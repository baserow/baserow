"""Experiment execution: task/evaluator adapters over ``run_case`` for Phoenix.

``run_experiment_for`` has two paths. With no ``case_ids`` it hands the whole
run loop to Phoenix's ``client.experiments.run_experiment`` over every example
in the dataset. The client has no per-example filter, so a ``--case`` subset
is instead run locally via ``run_case`` and posted with
``experiments.create`` + ``log_run``/``log_evaluation`` — the same primitives
``run_experiment`` itself is built on (per the installed client's docstrings),
making this the "precomputed run" upload path rather than a local-only,
unrecorded run.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.context import Context

from baserow_enterprise.assistant.evals.gitinfo import get_git_info
from baserow_enterprise.assistant.evals.harness import run_case
from baserow_enterprise.assistant.evals.judge import get_judge_model, judge_docs_answer
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.prompt_sync import prompt_hashes
from baserow_enterprise.assistant.evals.registry import get_case, load_all
from baserow_enterprise.assistant.evals.types import EvalCase
from baserow_enterprise.assistant.telemetry import get_assistant_tracer_provider
from baserow_enterprise.assistant.tools.search_user_docs.handler import (
    KnowledgeBaseHandler,
)


def _score_and_explanation(checks: list[dict[str, Any]]) -> tuple[float, str]:
    total = len(checks)
    if not total:
        return 0.0, ""
    passed_count = sum(1 for c in checks if c["passed"])
    explanation = "\n".join(
        f"✗ {c['name']} — {c['hint']}" for c in checks if not c["passed"]
    )
    return passed_count / total, explanation


def checklist(output: dict[str, Any]) -> dict[str, Any]:
    """Evaluator: fraction of checks that passed, plus failure detail.

    Skipped outputs (no ``checks`` were ever run) score an empty result — the
    Phoenix-valid way to record "no score" — so they don't count as 0.0 in
    aggregates. ``None`` is not an option: the installed phoenix-client
    scorer (``_default_eval_scorer``) raises ``ValueError`` on it.
    """

    if "skipped" in output:
        return {}
    score, explanation = _score_and_explanation(output.get("checks", []))
    # 2-tuples map position 1 to the LABEL in the phoenix client; 3-tuples don't.
    return {"score": score, "explanation": explanation or None}


def passed(output: dict[str, Any]) -> bool | dict[str, Any]:
    """Evaluator: whether every check (incl. the tool-error budget) passed.

    Skipped outputs score an empty result instead of the vacuous ``all([])
    is True``, so they don't count as passing in aggregates.
    """

    if "skipped" in output:
        return {}
    return all(c["passed"] for c in output.get("checks", []))


def run_case_for_experiment(
    case: EvalCase, model: str, kb_available: bool
) -> dict[str, Any]:
    """Run one case and shape the result as a Phoenix task/run output.

    Skips knowledge-base-gated cases without calling ``run_case`` when the
    knowledge base is unavailable, since the assistant can't answer them.
    """

    if case.requires_knowledge_base and not kb_available:
        return {"skipped": "knowledge base unavailable"}

    output, checks = run_case(case, model)
    check_dicts = [asdict(c) for c in checks]
    partial = {"checks": check_dicts}
    return {
        "answer": output.answer,
        "tool_calls": output.tool_calls,
        "tool_error_count": output.tool_error_count,
        "checks": check_dicts,
        "score": _score_and_explanation(check_dicts)[0],
        "passed": passed(partial),
        "sources": [str(s) for s in output.sources],
        "sources_count": len(output.sources),
        "request_count": output.request_count,
        "duration_s": output.duration_s,
    }


def answer_quality(
    output: dict[str, Any],
    metadata: dict[str, Any],
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-judge evaluator: scores a kuma-docs answer's correctness and groundedness.

    Runs only for docs cases (case id under ``docs/`` or the example's
    ``requires_knowledge_base`` metadata flag) with a non-skipped output.
    A judge failure — missing case, LLM error, anything — is logged and
    scores an empty result, the same as a skipped case, so it never poisons
    aggregates.

    ``expected`` is the dataset example's ``output`` — Phoenix's evaluator
    binder passes it by that name (an alias, ``reference``, also exists).
    """

    if "skipped" in output:
        return {}

    case_id = metadata.get("case_id") or ""
    is_docs_case = case_id.startswith("docs/") or metadata.get(
        "requires_knowledge_base", False
    )
    if not is_docs_case:
        return {}

    reference_answer = (expected or {}).get("reference_answer") or None

    try:
        case = get_case(case_id)
        verdict = judge_docs_answer(
            question=case.prompt,
            answer=output["answer"],
            sources=output.get("sources", []),
            keywords=metadata.get("expected_keywords", []),
            reference_answer=reference_answer,
        )
    except Exception:
        logger.warning("answer_quality judge failed for case {}", case_id)
        return {}

    return {"score": verdict.score, "explanation": verdict.explanation}


def _experiment_metadata(model: str, **extra: Any) -> dict[str, Any]:
    """Metadata every experiment gets: model, judge model, prompt hashes, git info.

    Lets branch/model/prompt-version comparisons be filtered in Phoenix.
    """

    return {
        "model": model,
        "judge_model": get_judge_model(),
        **extra,
        "prompts": prompt_hashes(),
        **get_git_info(),
    }


def run_experiment_for(
    dataset_name: str,
    model: str,
    case_ids: list[str] | None = None,
    runs: int = 1,
    experiment_name: str | None = None,
) -> Any:
    """Run (or resume as a subset) a Phoenix experiment for an eval dataset."""

    load_all()
    client = get_phoenix_client()
    kb_available = KnowledgeBaseHandler().can_search()

    if case_ids:
        return _run_case_subset(
            client, dataset_name, case_ids, model, runs, experiment_name, kb_available
        )

    def task(example: Any) -> dict[str, Any]:
        try:
            case = get_case(example.metadata.get("case_id"))
        except KeyError:
            return {"skipped": "ui example not yet promoted to code"}
        return run_case_for_experiment(case, model, kb_available)

    dataset = client.datasets.get_dataset(dataset=dataset_name)
    return client.experiments.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=[checklist, passed, answer_quality],
        experiment_name=experiment_name,
        experiment_metadata=_experiment_metadata(model),
        repetitions=runs,
    )


def _run_case_subset(
    client: Any,
    dataset_name: str,
    case_ids: list[str],
    model: str,
    runs: int,
    experiment_name: str | None,
    kb_available: bool,
) -> Any:
    dataset = client.datasets.get_dataset(dataset=dataset_name)
    # UI-added examples carry no case_id and are skipped here, not KeyError'd.
    examples_by_case_id = {
        case_id: ex
        for ex in dataset.examples
        if (case_id := ex.get("metadata", {}).get("case_id"))
    }
    try:
        selected = [examples_by_case_id[case_id] for case_id in case_ids]
    except KeyError as e:
        raise ValueError(
            f"Case {e.args[0]!r} was not found in Phoenix dataset "
            f"{dataset_name!r}; run `just b eval-sync` to sync it first."
        ) from None

    experiment = client.experiments.create(
        dataset_id=dataset.id,
        dataset_version_id=dataset.version_id,
        experiment_name=experiment_name,
        experiment_metadata=_experiment_metadata(model, case_ids=case_ids),
        repetitions=runs,
    )

    for example in selected:
        case = get_case(example["metadata"]["case_id"])
        for repetition in range(1, runs + 1):
            _log_case_run(
                client, experiment, example, case, model, kb_available, repetition
            )

    return client.experiments.get_experiment(experiment_id=experiment["id"])


def _log_case_run(
    client: Any,
    experiment: dict[str, Any],
    example: Any,
    case: EvalCase,
    model: str,
    kb_available: bool,
    repetition: int,
) -> None:
    provider = get_assistant_tracer_provider()
    tracer = provider.get_tracer(__name__) if provider else trace.get_tracer(__name__)
    start = datetime.now(timezone.utc)
    # Fresh Context() per case so each root span starts its own trace.
    with tracer.start_as_current_span(f"Task: {case.id}", context=Context()) as span:
        result = run_case_for_experiment(case, model, kb_available)
        span_context = span.get_span_context()
    end = datetime.now(timezone.utc)

    trace_id = None
    if span_context is not None and span_context.trace_id:
        trace_id = format(span_context.trace_id, "032x")

    run = client.experiments.log_run(
        experiment_id=experiment["id"],
        dataset_example_id=example.get("node_id") or example["id"],
        output=result,
        start_time=start,
        end_time=end,
        repetition_number=repetition,
        trace_id=trace_id,
    )

    if "skipped" in result:
        return

    score, explanation = _score_and_explanation(result.get("checks", []))
    client.experiments.log_evaluation(
        experiment_run_id=run["id"],
        name="checklist",
        score=score,
        explanation=explanation,
    )
    case_passed = passed(result)
    client.experiments.log_evaluation(
        experiment_run_id=run["id"],
        name="passed",
        score=float(case_passed),
        label=str(case_passed),
    )

    quality = answer_quality(result, example["metadata"], example.get("output"))
    if quality:
        client.experiments.log_evaluation(
            experiment_run_id=run["id"],
            name="answer_quality",
            score=quality["score"],
            explanation=quality["explanation"],
        )
