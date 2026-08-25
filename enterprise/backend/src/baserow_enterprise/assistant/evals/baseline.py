"""Committed baseline snapshot: capture experiment results from Phoenix and
import them into any (fresh) instance as a ``baseline`` experiment per
dataset, so every later run has a stable comparison column without re-running
the suite.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

import httpx
from loguru import logger

from baserow_enterprise.assistant.evals.registry import cases_by_dataset

BASELINE_PATH = Path(__file__).with_name("baseline.json")
BASELINE_EXPERIMENT_NAME = "baseline"

_ANNOTATIONS_QUERY = """
query ($runId: ID!) {
  node(id: $runId) {
    ... on ExperimentRun {
      annotations { edges { node { name score label explanation } } }
    }
  }
}
"""


def _api_base() -> str:
    base = os.getenv("PHOENIX_ENDPOINT") or getattr(
        settings, "BASEROW_ASSISTANT_PHOENIX_URL", ""
    )
    return base.rstrip("/")


def _headers() -> dict[str, str]:
    api_key = os.getenv("PHOENIX_API_KEY") or getattr(
        settings, "BASEROW_ASSISTANT_PHOENIX_API_KEY", ""
    )
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

    response = httpx.post(
        f"{_api_base()}/graphql",
        json={"query": _ANNOTATIONS_QUERY, "variables": {"runId": run_id}},
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    edges = response.json()["data"]["node"]["annotations"]["edges"]
    return [edge["node"] for edge in edges if _has_result(edge["node"])]


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot["datasets"], sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def capture_baseline(client: Any, experiment_name: str | None = None) -> dict[str, str]:
    """Snapshot the newest experiment per dataset into ``baseline.json``.

    ``experiment_name`` restricts the pick to experiments with that name —
    use it to capture a deliberate baseline run rather than whatever ran
    last. Registry must be loaded (``load_all``) before calling.
    """

    snapshot: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
    }
    results: dict[str, str] = {}

    for dataset_name in cases_by_dataset():
        dataset = client.datasets.get_dataset(dataset=dataset_name)
        experiments = _get(f"/v1/datasets/{dataset.id}/experiments")
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
            "runs": runs,
        }
        results[dataset_name] = (
            f"captured {len(runs)} runs from '{experiment.get('name')}'"
            + (f" ({skipped} non-code runs skipped)" if skipped else "")
        )

    BASELINE_PATH.write_text(json.dumps(snapshot, indent=2) + "\n")
    results["file"] = str(BASELINE_PATH)
    return results


def import_baseline(client: Any) -> dict[str, str]:
    """Create a ``baseline`` experiment per dataset from ``baseline.json``.

    Idempotent: a dataset already holding an experiment stamped with this
    snapshot's content hash is left alone. Cases that no longer exist in the
    live dataset are skipped with a count.
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

        # Complete-only idempotency: a hash-stamped experiment that crashed
        # mid-import (fewer runs than the snapshot) is superseded, not kept.
        experiments = _get(f"/v1/datasets/{dataset.id}/experiments")
        if any(
            (e.get("metadata") or {}).get("baseline_snapshot_hash") == content_hash
            and (e.get("successful_run_count") or 0) >= len(data["runs"])
            for e in experiments
        ):
            results[dataset_name] = "already imported"
            continue

        node_by_case_id = {
            example["metadata"]["case_id"]: example.get("node_id") or example["id"]
            for example in dataset.examples
            if example.get("metadata", {}).get("case_id")
        }

        experiment = client.experiments.create(
            dataset_id=dataset.id,
            dataset_version_id=dataset.version_id,
            experiment_name=BASELINE_EXPERIMENT_NAME,
            experiment_metadata={
                **data.get("metadata", {}),
                "baseline": True,
                "baseline_snapshot_hash": content_hash,
                "captured_at": snapshot.get("captured_at"),
            },
            repetitions=max(
                (run["repetition_number"] for run in data["runs"]), default=1
            ),
        )

        imported = skipped = 0
        for run in data["runs"]:
            node_id = node_by_case_id.get(run["case_id"])
            if node_id is None:
                skipped += 1
                continue
            logged = client.experiments.log_run(
                experiment_id=experiment["id"],
                dataset_example_id=node_id,
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
            imported += 1

        results[dataset_name] = f"imported {imported} runs" + (
            f" ({skipped} removed cases skipped)" if skipped else ""
        )
        logger.info("Baseline import for '{}': {}", dataset_name, results[dataset_name])

    return results
