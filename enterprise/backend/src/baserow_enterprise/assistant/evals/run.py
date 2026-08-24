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

from baserow_enterprise.assistant.evals.harness import run_case
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.registry import get_case, load_all
from baserow_enterprise.assistant.evals.types import EvalCase
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


def checklist(output: dict[str, Any]) -> tuple[float, str]:
    """Evaluator: fraction of checks that passed, plus failure detail."""

    return _score_and_explanation(output.get("checks", []))


def passed(output: dict[str, Any]) -> bool:
    """Evaluator: whether every check (incl. the tool-error budget) passed."""

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
        "score": checklist(partial)[0],
        "passed": passed(partial),
        "sources_count": len(output.sources),
        "request_count": output.request_count,
        "duration_s": output.duration_s,
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
        case = get_case(example.metadata["case_id"])
        return run_case_for_experiment(case, model, kb_available)

    dataset = client.datasets.get_dataset(dataset=dataset_name)
    return client.experiments.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=[checklist, passed],
        experiment_name=experiment_name,
        experiment_metadata={"model": model},
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
    examples_by_case_id = {ex["metadata"]["case_id"]: ex for ex in dataset.examples}
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
        experiment_metadata={"model": model, "case_ids": case_ids},
        repetitions=runs,
    )

    for example in selected:
        case = get_case(example["metadata"]["case_id"])
        for repetition in range(1, runs + 1):
            _log_case_run(
                client, experiment, example, case, model, kb_available, repetition
            )

    return experiment


def _log_case_run(
    client: Any,
    experiment: dict[str, Any],
    example: Any,
    case: EvalCase,
    model: str,
    kb_available: bool,
    repetition: int,
) -> None:
    start = datetime.now(timezone.utc)
    result = run_case_for_experiment(case, model, kb_available)
    end = datetime.now(timezone.utc)

    run = client.experiments.log_run(
        experiment_id=experiment["id"],
        dataset_example_id=example.get("node_id") or example["id"],
        output=result,
        start_time=start,
        end_time=end,
        repetition_number=repetition,
    )

    score, explanation = checklist(result)
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
