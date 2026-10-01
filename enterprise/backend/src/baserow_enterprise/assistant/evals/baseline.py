"""Committed baseline snapshot: capture experiment results from Phoenix and
import them into any (fresh) instance as a ``baseline (imported)`` experiment
per dataset for historical inspection without re-running the suite.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

import httpx
from loguru import logger

from baserow_enterprise.assistant.evals.registry import cases_by_dataset

BASELINE_PATH = Path(__file__).with_name("baseline.json")
BASELINE_EXPERIMENT_NAME = "baseline (imported)"

_ANNOTATIONS_QUERY = """
query ($runId: ID!) {
  node(id: $runId) {
    ... on ExperimentRun {
      annotations { edges { node { name score label explanation } } }
    }
  }
}
"""

_EXPERIMENT_TOTALS_QUERY = """
query ($experimentId: ID!) {
  node(id: $experimentId) {
    ... on Experiment {
      runCount
      averageRunLatencyMs
      costSummary { total { cost tokens } }
    }
  }
}
"""

_DELETE_EXPERIMENTS_MUTATION = """
mutation ($ids: [ID!]!) {
  deleteExperiments(input: {experimentIds: $ids}) { __typename }
}
"""


def _api_base() -> str:
    base = getattr(settings, "BASEROW_ASSISTANT_PHOENIX_URL", "")
    return base.rstrip("/")


def _headers() -> dict[str, str]:
    api_key = getattr(settings, "BASEROW_ASSISTANT_PHOENIX_API_KEY", "")
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _get(path: str) -> Any:
    response = httpx.get(f"{_api_base()}{path}", headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()["data"]


def _has_result(annotation: dict[str, Any]) -> bool:
    return (
        annotation.get("score") is not None
        or bool(annotation.get("label"))
        or bool(annotation.get("explanation"))
    )


def _run_annotations(run_id: str) -> list[dict[str, Any]]:
    """A run's scored annotations; no-score markers (empty evaluator results
    for non-applicable evaluators) are dropped — they carry no information
    and Phoenix refuses to log them back."""

    data = _graphql(_ANNOTATIONS_QUERY, {"runId": run_id})
    edges = data["node"]["annotations"]["edges"]
    return [edge["node"] for edge in edges if _has_result(edge["node"])]


def _graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{_api_base()}/graphql",
        json={"query": query, "variables": variables},
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["data"]


def _experiment_totals(experiment_id: str) -> dict[str, Any]:
    """Run-time and cost totals for an experiment, for freezing into the
    snapshot — imported baselines carry no traces to derive them from."""

    node = _graphql(_EXPERIMENT_TOTALS_QUERY, {"experimentId": experiment_id})["node"]
    cost_total = (node.get("costSummary") or {}).get("total") or {}
    return {
        "run_count": node.get("runCount"),
        "average_run_latency_ms": node.get("averageRunLatencyMs"),
        "total_cost": cost_total.get("cost"),
        "total_tokens": cost_total.get("tokens"),
    }


def _delete_experiments(experiment_ids: list[str]) -> None:
    _graphql(_DELETE_EXPERIMENTS_MUTATION, {"ids": experiment_ids})


def _mark_import_complete(experiment_id: str, metadata: dict[str, Any]) -> None:
    """Mark an import complete only after its runs and annotations were saved."""

    response = httpx.patch(
        f"{_api_base()}/v1/experiments/{experiment_id}",
        json={"metadata": {**metadata, "baseline_import_complete": True}},
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()


def _delete_stale_imports(
    experiments: list[dict[str, Any]], dataset_name: str, keep_id: str
) -> None:
    """Remove replaced imports, preserving live experiments regardless of name."""

    stale_ids = [
        experiment["id"]
        for experiment in experiments
        if experiment["id"] != keep_id
        and (experiment.get("metadata") or {}).get("baseline_snapshot_hash")
    ]
    if not stale_ids:
        return
    try:
        _delete_experiments(stale_ids)
        logger.info(
            "Superseded {} imported baseline experiment(s) for '{}'",
            len(stale_ids),
            dataset_name,
        )
    except Exception as exc:
        logger.warning(
            "Could not delete stale baseline imports for '{}': {}", dataset_name, exc
        )


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot["datasets"], sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def capture_baseline(client: Any, experiment_name: str | None = None) -> dict[str, str]:
    """Snapshot the newest experiment per dataset into ``baseline.json``.

    ``experiment_name`` restricts the pick to experiments with that name —
    use it to capture a deliberate baseline run rather than whatever ran
    last. Errored code runs abort capture without replacing the snapshot.
    Registry must be loaded (``load_all``) before calling.
    """

    snapshot: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
    }
    results: dict[str, str] = {}

    for dataset_name in cases_by_dataset():
        dataset = client.datasets.get_dataset(dataset=dataset_name)
        experiments = client.experiments.list(dataset_id=dataset.id)
        if experiment_name:
            experiments = [e for e in experiments if e.get("name") == experiment_name]
        if not experiments:
            results[dataset_name] = "no matching experiment"
            continue
        experiment = experiments[0]

        case_id_by_node = {
            (example.get("node_id") or example["id"]): example["metadata"]["case_id"]
            for example in dataset.examples
            if example.get("metadata", {}).get("case_id")
        }

        runs = []
        skipped = 0
        for run in _get(f"/v1/experiments/{experiment['id']}/runs"):
            case_id = case_id_by_node.get(run["dataset_example_id"])
            if not case_id:
                skipped += 1
                continue
            if run.get("error") is not None:
                raise ValueError(
                    f"Cannot capture baseline for '{dataset_name}': experiment "
                    f"'{experiment['id']}' has an errored run for '{case_id}': "
                    f"{run['error']}"
                )
            runs.append(
                {
                    "case_id": case_id,
                    "repetition_number": run.get("repetition_number") or 1,
                    "start_time": run["start_time"],
                    "end_time": run["end_time"],
                    "output": run["output"],
                    "annotations": _run_annotations(run["id"]),
                }
            )

        snapshot["datasets"][dataset_name] = {
            "experiment_name": experiment.get("name"),
            "metadata": experiment.get("metadata") or {},
            "totals": _experiment_totals(experiment["id"]),
            "runs": runs,
        }
        results[dataset_name] = (
            f"captured {len(runs)} runs from '{experiment.get('name')}'"
            + (f" ({skipped} non-code runs skipped)" if skipped else "")
        )

    BASELINE_PATH.write_text(_dump_snapshot(snapshot))
    results["file"] = str(BASELINE_PATH)
    return results


def _dump_snapshot(snapshot: dict[str, Any]) -> str:
    """Serialize with one compact line per run.

    :param snapshot: The captured baseline snapshot.
    :return: JSON text that parses back to *snapshot* exactly.
    """

    compact = (",", ":")
    lines = ["{", f'  "captured_at": {json.dumps(snapshot["captured_at"])},']
    lines.append('  "datasets": {')
    ds_items = list(snapshot["datasets"].items())
    for di, (name, data) in enumerate(ds_items):
        lines.append(f"    {json.dumps(name)}: {{")
        for key in ("experiment_name", "metadata", "totals"):
            value = json.dumps(data[key], separators=compact)
            lines.append(f"      {json.dumps(key)}: {value},")
        lines.append('      "runs": [')
        for ri, run in enumerate(data["runs"]):
            comma = "," if ri < len(data["runs"]) - 1 else ""
            lines.append(f"        {json.dumps(run, separators=compact)}{comma}")
        lines.append("      ]")
        lines.append("    }" + ("," if di < len(ds_items) - 1 else ""))
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def import_baseline(client: Any) -> dict[str, str]:
    """Create historical experiments from ``baseline.json``, separate from live runs.

    Completed imports for the same snapshot and dataset version are retained.
    Removed cases are skipped. Interrupted and legacy imports are replaced only
    after the new import has saved every applicable run and annotation.
    A failed attempt deletes only its own newly created experiment.
    """

    if not BASELINE_PATH.exists():
        return {"status": "no baseline snapshot committed"}
    snapshot = json.loads(BASELINE_PATH.read_text())
    content_hash = _snapshot_hash(snapshot)
    results: dict[str, str] = {}

    for dataset_name, data in snapshot["datasets"].items():
        try:
            dataset = client.datasets.get_dataset(dataset=dataset_name)
        except Exception:
            results[dataset_name] = "dataset not found in Phoenix"
            continue

        node_by_case_id = {
            example["metadata"]["case_id"]: example.get("node_id") or example["id"]
            for example in dataset.examples
            if example.get("metadata", {}).get("case_id")
        }
        applicable_runs = [
            run for run in data["runs"] if run["case_id"] in node_by_case_id
        ]
        skipped = len(data["runs"]) - len(applicable_runs)
        if not applicable_runs:
            results[dataset_name] = "no snapshot cases in the current dataset"
            continue

        experiments = client.experiments.list(dataset_id=dataset.id)
        completed_import = next(
            (
                experiment
                for experiment in experiments
                if experiment.get("name") == BASELINE_EXPERIMENT_NAME
                and experiment.get("dataset_version_id") == dataset.version_id
                and (experiment.get("metadata") or {}).get("baseline_snapshot_hash")
                == content_hash
                and (experiment.get("metadata") or {}).get("baseline_import_complete")
                is True
                and (experiment.get("successful_run_count") or 0)
                >= len(applicable_runs)
            ),
            None,
        )
        if completed_import is not None:
            # A previous import may have finished before its cleanup was interrupted.
            _delete_stale_imports(experiments, dataset_name, completed_import["id"])
            results[dataset_name] = "already imported"
            continue

        import_metadata = {
            **data.get("metadata", {}),
            "baseline": True,
            "baseline_snapshot_hash": content_hash,
            "baseline_import_complete": False,
            "baseline_totals": data.get("totals") or {},
            "captured_at": snapshot.get("captured_at"),
        }
        experiment = client.experiments.create(
            dataset_id=dataset.id,
            dataset_version_id=dataset.version_id,
            experiment_name=BASELINE_EXPERIMENT_NAME,
            experiment_metadata=import_metadata,
            repetitions=max(run["repetition_number"] for run in applicable_runs),
        )

        try:
            for run in applicable_runs:
                logged = client.experiments.log_run(
                    experiment_id=experiment["id"],
                    dataset_example_id=node_by_case_id[run["case_id"]],
                    output=run["output"],
                    start_time=datetime.fromisoformat(run["start_time"]),
                    end_time=datetime.fromisoformat(run["end_time"]),
                    repetition_number=run["repetition_number"],
                )
                for annotation in run.get("annotations", []):
                    if not _has_result(annotation):
                        continue
                    client.experiments.log_evaluation(
                        experiment_run_id=logged["id"],
                        name=annotation["name"],
                        score=annotation.get("score"),
                        label=annotation.get("label"),
                        explanation=annotation.get("explanation"),
                    )
            _mark_import_complete(experiment["id"], import_metadata)
        except Exception:
            try:
                client.experiments.delete(experiment_id=experiment["id"])
            except Exception as exc:
                logger.warning(
                    "Could not delete failed baseline import '{}' for '{}': {}",
                    experiment["id"],
                    dataset_name,
                    exc,
                )
            raise
        _delete_stale_imports(experiments, dataset_name, experiment["id"])

        results[dataset_name] = f"imported {len(applicable_runs)} runs" + (
            f" ({skipped} removed cases skipped)" if skipped else ""
        )
        logger.info("Baseline import for '{}': {}", dataset_name, results[dataset_name])

    return results
