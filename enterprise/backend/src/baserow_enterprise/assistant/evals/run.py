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

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode

from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.control import RunControl
from baserow_enterprise.assistant.evals.gitinfo import get_git_info
from baserow_enterprise.assistant.evals.harness import (
    EvalCaseTimeout,
    get_case_timeout_s,
    override_assistant_prompts,
    run_case,
    tool_called,
)
from baserow_enterprise.assistant.evals.judge import get_judge_model, judge_docs_answer
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.prompt_sync import (
    SYNCED_PROMPTS,
    _template_text,
    prompt_hashes,
)
from baserow_enterprise.assistant.evals.registry import (
    all_cases,
    get_case,
    get_scenario,
    load_all,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    CheckSuite,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    get_model_settings,
)
from baserow_enterprise.assistant.telemetry import get_assistant_tracer_provider
from baserow_enterprise.assistant.tools.search_user_docs.handler import (
    KnowledgeBaseHandler,
)

UI_CASE_PREFIX = "ui:"

_PROMPT_INPUT_KEYS = ("prompt", "question", "input", "message")


def prompt_from_example_input(example_input: Any) -> str | None:
    """Extract the prompt from a Phoenix example's ``input``, leniently.

    UI authors and add-from-span produce varying shapes; accept a bare string,
    any conventional key, or a single-string-valued dict.
    """

    if isinstance(example_input, str) and example_input.strip():
        return example_input.strip()
    if not isinstance(example_input, dict):
        return None
    for key in _PROMPT_INPUT_KEYS:
        value = example_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    values = [v for v in example_input.values() if isinstance(v, str) and v.strip()]
    if len(values) == 1:
        return values[0].strip()
    return None


def _dataset_default_mode(dataset_name: str) -> AgentMode:
    for case in all_cases():
        if case.dataset == dataset_name:
            return case.mode
    return AgentMode.DATABASE


def _int_or(metadata: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(metadata.get(key, default))
    except (TypeError, ValueError):
        return default


def _str_list(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _adhoc_checks(
    metadata: dict[str, Any], requires_knowledge_base: bool
) -> CheckSuite:
    """Declarative checks for a UI-added example, built from its metadata."""

    expected_tools = _str_list(metadata, "expected_tools")
    answer_contains = _str_list(metadata, "answer_contains")
    expected_keywords = _str_list(metadata, "expected_keywords")

    def _checks(
        case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
    ) -> list[CheckResult]:
        answer = output.answer.lower()
        results = []
        if requires_knowledge_base:
            results.append(
                CheckResult(
                    "called search_user_docs",
                    tool_called(output, "search_user_docs") >= 1,
                    hint=f"tools called: {output.tool_calls}",
                )
            )
            results.append(
                CheckResult(
                    "returned at least one source URL",
                    len(output.sources) >= 1,
                    hint=f"tools called: {output.tool_calls}",
                )
            )
            if expected_keywords:
                results.append(
                    CheckResult(
                        f"answer mentions one of {expected_keywords}",
                        any(kw.lower() in answer for kw in expected_keywords),
                        hint=output.answer[:300],
                    )
                )
        for tool in expected_tools:
            results.append(
                CheckResult(
                    f"called {tool}",
                    tool_called(output, tool) >= 1,
                    hint=f"tools called: {output.tool_calls}",
                )
            )
        for text in answer_contains:
            results.append(
                CheckResult(
                    f"answer contains '{text}'",
                    text.lower() in answer,
                    hint=output.answer[:300],
                )
            )
        return results

    return _checks


def case_for_example(
    example_input: Any,
    metadata: dict[str, Any],
    dataset_name: str,
    example_id: str,
) -> EvalCase | dict[str, Any]:
    """Resolve a dataset example to a runnable case, code-owned or ad-hoc.

    Code-owned examples (``case_id`` metadata) resolve through the registry.
    UI-added ones become an ad-hoc case: prompt from the example input,
    scenario/mode/checks from its metadata with per-dataset defaults.
    Unresolvable examples return a skipped-output dict instead of a case.
    """

    case_id = metadata.get("case_id")
    if case_id:
        try:
            return get_case(case_id)
        except KeyError:
            return {"skipped": f"unknown case id '{case_id}' — run eval-sync"}

    prompt = prompt_from_example_input(example_input)
    if not prompt:
        return {"skipped": "ui example has no prompt in its input"}

    requires_kb = bool(
        metadata.get("requires_knowledge_base", dataset_name == "kuma-docs")
    )
    default_scenario = "docs-question" if requires_kb else "empty-workspace"
    scenario_name = metadata.get("scenario") or default_scenario
    try:
        get_scenario(scenario_name)
    except KeyError:
        return {"skipped": f"unknown scenario '{scenario_name}'"}

    mode = _dataset_default_mode(dataset_name)
    if metadata.get("mode"):
        try:
            mode = AgentMode(metadata["mode"])
        except ValueError:
            pass

    return EvalCase(
        id=f"ui/{example_id}",
        dataset=dataset_name,
        prompt=prompt,
        scenario=scenario_name,
        checks=_adhoc_checks(metadata, requires_kb),
        mode=mode,
        max_iters=_int_or(metadata, "max_iters", 15),
        max_tool_errors=_int_or(metadata, "max_tool_errors", 0),
        requires_knowledge_base=requires_kb,
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


def _timed_out_result(case: EvalCase, reason: str) -> dict[str, Any]:
    """A timed-out case's Phoenix output: one failed check, so it scores 0."""

    checks = [{"name": "completed_within_timeout", "passed": False, "hint": reason}]
    return {
        "question": case.prompt,
        # No answer to grade, so don't spend a judge call on it.
        "judge_docs": False,
        "answer": "",
        "tool_calls": [],
        "tool_error_count": 0,
        "checks": checks,
        "score": 0.0,
        "passed": False,
        "timed_out": True,
        "sources": [],
        "sources_count": 0,
        "request_count": 0,
        "duration_s": get_case_timeout_s(),
    }


def run_case_for_experiment(
    case: EvalCase,
    model: str,
    kb_available: bool,
    prompt_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one case and shape the result as a Phoenix task/run output.

    Skips knowledge-base-gated cases without calling ``run_case`` when the
    knowledge base is unavailable, since the assistant can't answer them.
    ``prompt_texts`` swaps assistant prompts for the run's duration.
    """

    if case.requires_knowledge_base and not kb_available:
        logger.info("skip {} (knowledge base unavailable)", case.id)
        return {"skipped": "knowledge base unavailable"}

    logger.info("run {}", case.id)
    try:
        with override_assistant_prompts(prompt_texts or {}):
            output, checks = run_case(case, model)
    except EvalCaseTimeout as exc:
        # A hang is a real failure: score it 0 rather than skipping it, and
        # keep the remaining cases running.
        logger.warning("TIMEOUT {}", exc)
        return _timed_out_result(case, str(exc))
    check_dicts = [asdict(c) for c in checks]
    partial = {"checks": check_dicts}
    score = _score_and_explanation(check_dicts)[0]
    logger.info(
        "{} {} score {:.2f} in {:.1f}s ({} requests, {} tool errors)",
        "PASS" if passed(partial) is True else "FAIL",
        case.id,
        score,
        output.duration_s,
        output.request_count,
        output.tool_error_count,
    )
    return {
        "question": case.prompt,
        "judge_docs": case.requires_knowledge_base,
        "answer": output.answer,
        "tool_calls": output.tool_calls,
        "tool_error_count": output.tool_error_count,
        "checks": check_dicts,
        "score": score,
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

    Runs only for knowledge-base cases — the task marks those outputs with
    ``judge_docs`` (and carries the ``question``), so UI-added examples are
    judged the same way as code cases. A judge failure — LLM error,
    anything — is logged and scores an empty result, the same as a skipped
    case, so it never poisons aggregates.

    ``expected`` is the dataset example's ``output`` — Phoenix's evaluator
    binder passes it by that name (an alias, ``reference``, also exists).
    """

    if "skipped" in output or not output.get("judge_docs"):
        return {}

    reference_answer = (expected or {}).get("reference_answer") or None

    try:
        verdict = judge_docs_answer(
            question=output.get("question", ""),
            answer=output["answer"],
            sources=output.get("sources", []),
            keywords=metadata.get("expected_keywords", []),
            reference_answer=reference_answer,
        )
    except Exception:
        logger.warning(
            "answer_quality judge failed for question {}", output.get("question")
        )
        return {}

    return {"score": verdict.score, "explanation": verdict.explanation}


def _fetch_prompt_overrides(client: Any, names: list[str] | None) -> dict[str, str]:
    """Fetch the latest Phoenix version text for each named prompt."""

    texts: dict[str, str] = {}
    for name in names or []:
        if name not in SYNCED_PROMPTS:
            raise ValueError(f"Unknown assistant prompt '{name}'")
        version = client.prompts.get(prompt_identifier=name)
        texts[name] = _template_text(version)
    return texts


def _experiment_metadata(
    model: str,
    prompt_texts: dict[str, str] | None = None,
    notes: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Metadata every experiment gets: model, settings, judge, prompt hashes, git.

    Lets branch/model/prompt-version comparisons be filtered in Phoenix.
    Overridden prompts are stamped with their effective (fetched) hash and
    listed under ``prompt_overrides``. ``model_settings`` records the resolved
    orchestrator profile so a run's temperature and reasoning effort are
    recoverable from the experiment alone.
    """

    hashes = prompt_hashes()
    for name, text in (prompt_texts or {}).items():
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()[:12]

    metadata = {
        "model": model,
        "model_settings": dict(get_model_settings(model, ORCHESTRATOR)),
        "judge_model": get_judge_model(),
        **extra,
        "prompts": hashes,
        **get_git_info(),
    }
    if prompt_texts:
        metadata["prompt_overrides"] = sorted(prompt_texts)
    if notes:
        metadata["notes"] = notes
    return metadata


def run_experiment_for(
    dataset_name: str,
    model: str,
    case_ids: list[str] | None = None,
    runs: int = 1,
    experiment_name: str | None = None,
    prompt_overrides: list[str] | None = None,
    notes: str | None = None,
    control: RunControl | None = None,
) -> Any:
    """Run (or resume as a subset) a Phoenix experiment for an eval dataset.

    ``prompt_overrides`` names synced prompts to run with their latest
    Phoenix version instead of the code constant. ``control`` receives
    per-case progress and is polled between cases so a run can be stopped.
    """

    load_all()
    control = control or RunControl()
    client = get_phoenix_client()
    kb_available = KnowledgeBaseHandler().can_search()
    prompt_texts = _fetch_prompt_overrides(client, prompt_overrides)

    if case_ids:
        return _run_case_subset(
            client,
            dataset_name,
            case_ids,
            model,
            runs,
            experiment_name,
            kb_available,
            prompt_texts,
            notes,
            control,
        )

    # Phoenix re-enters the task on retry, so cap each example at its repetitions.
    counted: Counter[str] = Counter()

    def task(example: Any) -> dict[str, Any]:
        if control.stopping:
            return {"skipped": "run stopped"}
        case = case_for_example(
            example.input, example.metadata, dataset_name, str(example.id)
        )
        if isinstance(case, dict):
            result = case
        else:
            result = run_case_for_experiment(case, model, kb_available, prompt_texts)
        example_id = str(example.id)
        if counted[example_id] < runs:
            counted[example_id] += 1
            control.case_finished()
        return result

    dataset = client.datasets.get_dataset(dataset=dataset_name)
    control.set_total(len(dataset.examples) * runs)
    return client.experiments.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=[checklist, passed, answer_quality],
        experiment_name=experiment_name,
        experiment_metadata=_experiment_metadata(model, prompt_texts, notes),
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
    prompt_texts: dict[str, str] | None = None,
    notes: str | None = None,
    control: RunControl | None = None,
) -> Any:
    control = control or RunControl()
    dataset = client.datasets.get_dataset(dataset=dataset_name)
    examples_by_case_id = {
        case_id: ex
        for ex in dataset.examples
        if (case_id := ex.get("metadata", {}).get("case_id"))
    }
    examples_by_example_id = {str(ex["id"]): ex for ex in dataset.examples}

    selected: list[tuple[dict[str, Any], EvalCase | dict[str, Any]]] = []
    for case_id in case_ids:
        if case_id.startswith(UI_CASE_PREFIX):
            example_id = case_id.split(":", 2)[2]
            example = examples_by_example_id.get(example_id)
            if example is None:
                raise ValueError(
                    f"UI example {example_id!r} was not found in Phoenix dataset "
                    f"{dataset_name!r}; it may have been deleted."
                )
            case = case_for_example(
                example.get("input", {}),
                example.get("metadata", {}),
                dataset_name,
                example_id,
            )
        else:
            example = examples_by_case_id.get(case_id)
            if example is None:
                raise ValueError(
                    f"Case {case_id!r} was not found in Phoenix dataset "
                    f"{dataset_name!r}; run `just b eval-sync` to sync it first."
                )
            case = get_case(case_id)
        selected.append((example, case))

    experiment = client.experiments.create(
        dataset_id=dataset.id,
        dataset_version_id=dataset.version_id,
        experiment_name=experiment_name,
        experiment_metadata=_experiment_metadata(
            model, prompt_texts, notes, case_ids=case_ids
        ),
        repetitions=runs,
    )

    control.set_total(len(selected) * runs)
    for example, case in selected:
        for repetition in range(1, runs + 1):
            if control.stopping:
                return client.experiments.get_experiment(experiment_id=experiment["id"])
            _log_case_run(
                client,
                experiment,
                example,
                case,
                model,
                kb_available,
                repetition,
                prompt_texts,
            )
            control.case_finished()

    return client.experiments.get_experiment(experiment_id=experiment["id"])


def _log_case_run(
    client: Any,
    experiment: dict[str, Any],
    example: Any,
    case: EvalCase | dict[str, Any],
    model: str,
    kb_available: bool,
    repetition: int,
    prompt_texts: dict[str, str] | None = None,
) -> None:
    trace_id = None
    if isinstance(case, dict):
        result = case
        start = end = datetime.now(timezone.utc)
    else:
        provider = get_assistant_tracer_provider()
        tracer = (
            provider.get_tracer(__name__) if provider else trace.get_tracer(__name__)
        )
        start = datetime.now(timezone.utc)
        # Fresh Context() per case so each root span starts its own trace.
        # OpenInference attributes make Phoenix render kind/input/output
        # instead of "unknown" with empty columns.
        with tracer.start_as_current_span(
            f"Task: {case.id}",
            context=Context(),
            attributes={
                SpanAttributes.OPENINFERENCE_SPAN_KIND: (
                    OpenInferenceSpanKindValues.CHAIN.value
                ),
                SpanAttributes.INPUT_VALUE: case.prompt,
                SpanAttributes.INPUT_MIME_TYPE: "text/plain",
            },
        ) as span:
            result = run_case_for_experiment(case, model, kb_available, prompt_texts)
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps(result))
            span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
            span.set_status(Status(StatusCode.OK))
            span_context = span.get_span_context()
        end = datetime.now(timezone.utc)

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
