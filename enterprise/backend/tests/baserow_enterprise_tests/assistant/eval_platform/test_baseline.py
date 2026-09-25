from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from baserow_enterprise.assistant.evals import baseline, registry
from baserow_enterprise.assistant.evals.baseline import (
    capture_baseline,
    import_baseline,
)
from baserow_enterprise.assistant.evals.types import EvalCase


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})
    registry.register_case(
        EvalCase(
            id="database/list-tables",
            dataset="kuma-database",
            prompt="p",
            scenario="s",
            checks=lambda c, s, o: [],
        )
    )


@pytest.fixture(autouse=True)
def _baseline_file(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "BASELINE_PATH", tmp_path / "baseline.json")


class _FakeDataset:
    def __init__(self, examples):
        self.id = "ds-1"
        self.version_id = "v1"
        self.examples = examples


class _FakeExperimentsAPI:
    def __init__(self):
        self.create_calls: list[dict] = []
        self.log_run_calls: list[dict] = []
        self.log_evaluation_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"id": "exp-baseline"}

    def log_run(self, **kwargs):
        self.log_run_calls.append(kwargs)
        return {"id": f"run-{len(self.log_run_calls)}"}

    def log_evaluation(self, **kwargs):
        self.log_evaluation_calls.append(kwargs)


class _FakeClient:
    def __init__(self, examples):
        self.experiments = _FakeExperimentsAPI()
        self._dataset = _FakeDataset(examples)
        self.datasets = self

    def get_dataset(self, dataset):
        return self._dataset


_CODE_EXAMPLE = {
    "id": "database/list-tables",
    "node_id": "node-1",
    "metadata": {"case_id": "database/list-tables"},
}


def _run_payload(example_id="node-1"):
    return {
        "id": "run-raw-1",
        "dataset_example_id": example_id,
        "repetition_number": 1,
        "start_time": "2026-08-25T10:00:00+00:00",
        "end_time": "2026-08-25T10:00:30+00:00",
        "output": {"answer": "the answer", "checks": []},
    }


class TestCaptureBaseline:
    def test_captures_newest_experiment_with_case_id_mapping(self):
        client = _FakeClient([_CODE_EXAMPLE])
        rest = {
            "/v1/datasets/ds-1/experiments": [
                {"id": "exp-2", "name": "latest", "metadata": {"model": "m"}},
                {"id": "exp-1", "name": "older", "metadata": {}},
            ],
            "/v1/experiments/exp-2/runs": [
                _run_payload(),
                _run_payload(example_id="foreign-node"),
            ],
        }

        totals = {
            "run_count": 2,
            "average_run_latency_ms": 6000.0,
            "total_cost": 0.05,
            "total_tokens": 120000,
        }
        with (
            patch.object(baseline, "_get", side_effect=lambda path: rest[path]),
            patch.object(
                baseline,
                "_run_annotations",
                return_value=[{"name": "passed", "score": 1.0}],
            ),
            patch.object(baseline, "_experiment_totals", return_value=totals),
        ):
            results = capture_baseline(client)

        assert "captured 1 runs from 'latest'" in results["kuma-database"]
        assert "1 non-code runs skipped" in results["kuma-database"]
        snapshot = json.loads(baseline.BASELINE_PATH.read_text())
        dataset_entry = snapshot["datasets"]["kuma-database"]
        run = dataset_entry["runs"][0]
        assert run["case_id"] == "database/list-tables"
        assert run["annotations"] == [{"name": "passed", "score": 1.0}]
        assert dataset_entry["totals"] == totals

    def test_experiment_name_filter_and_missing_experiment(self):
        client = _FakeClient([_CODE_EXAMPLE])
        rest = {
            "/v1/datasets/ds-1/experiments": [
                {"id": "exp-2", "name": "other", "metadata": {}},
            ],
        }

        with patch.object(baseline, "_get", side_effect=lambda path: rest[path]):
            results = capture_baseline(client, experiment_name="baseline-candidate")

        assert results["kuma-database"] == "no matching experiment"
        snapshot = json.loads(baseline.BASELINE_PATH.read_text())
        assert snapshot["datasets"] == {}


def _snapshot(runs):
    return {
        "captured_at": "2026-08-25T10:05:00+00:00",
        "datasets": {
            "kuma-database": {
                "experiment_name": "latest",
                "metadata": {"model": "m"},
                "totals": {"total_cost": 0.05, "total_tokens": 120000},
                "runs": runs,
            }
        },
    }


def _snapshot_run(case_id="database/list-tables"):
    return {
        "case_id": case_id,
        "repetition_number": 1,
        "start_time": "2026-08-25T10:00:00+00:00",
        "end_time": "2026-08-25T10:00:30+00:00",
        "output": {"answer": "the answer"},
        "annotations": [{"name": "passed", "score": 1.0, "label": "True"}],
    }


class TestImportBaseline:
    def test_no_snapshot_file(self):
        assert import_baseline(_FakeClient([])) == {
            "status": "no baseline snapshot committed"
        }

    def test_imports_runs_and_evaluations_and_skips_removed_cases(self):
        baseline.BASELINE_PATH.write_text(
            json.dumps(_snapshot([_snapshot_run(), _snapshot_run("database/gone")]))
        )
        client = _FakeClient([_CODE_EXAMPLE])

        with patch.object(baseline, "_get", return_value=[]):
            results = import_baseline(client)

        assert results["kuma-database"] == "imported 1 runs (1 removed cases skipped)"
        create = client.experiments.create_calls[0]
        assert create["experiment_name"] == "baseline"
        assert create["experiment_metadata"]["baseline"] is True
        assert create["experiment_metadata"]["model"] == "m"
        assert create["experiment_metadata"]["baseline_totals"] == {
            "total_cost": 0.05,
            "total_tokens": 120000,
        }
        assert client.experiments.log_run_calls[0]["dataset_example_id"] == "node-1"
        assert client.experiments.log_evaluation_calls[0]["name"] == "passed"

    def test_import_supersedes_stale_named_baseline_experiments(self):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        client = _FakeClient([_CODE_EXAMPLE])
        existing = [
            {
                "id": "exp-old-baseline",
                "name": "baseline",
                "metadata": {"baseline_snapshot_hash": "oldhash123456"},
                "successful_run_count": 1,
            }
        ]

        with (
            patch.object(baseline, "_get", return_value=existing),
            patch.object(baseline, "_delete_experiments") as mock_delete,
        ):
            results = import_baseline(client)

        mock_delete.assert_called_once_with(["exp-old-baseline"])
        assert results["kuma-database"] == "imported 1 runs"

    def test_import_is_idempotent_by_snapshot_hash(self):
        snapshot = _snapshot([_snapshot_run()])
        baseline.BASELINE_PATH.write_text(json.dumps(snapshot))
        content_hash = baseline._snapshot_hash(snapshot)
        client = _FakeClient([_CODE_EXAMPLE])
        existing = [
            {
                "metadata": {"baseline_snapshot_hash": content_hash},
                "successful_run_count": 1,
            }
        ]

        with patch.object(baseline, "_get", return_value=existing):
            results = import_baseline(client)

        assert results["kuma-database"] == "already imported"
        assert client.experiments.create_calls == []

    def test_incomplete_hash_matching_experiment_is_superseded(self):
        snapshot = _snapshot([_snapshot_run()])
        baseline.BASELINE_PATH.write_text(json.dumps(snapshot))
        content_hash = baseline._snapshot_hash(snapshot)
        client = _FakeClient([_CODE_EXAMPLE])
        existing = [
            {
                "metadata": {"baseline_snapshot_hash": content_hash},
                "successful_run_count": 0,
            }
        ]

        with patch.object(baseline, "_get", return_value=existing):
            results = import_baseline(client)

        assert results["kuma-database"] == "imported 1 runs"
        assert len(client.experiments.create_calls) == 1

    def test_import_drops_no_result_annotations(self):
        run = _snapshot_run()
        run["annotations"].append(
            {"name": "answer_quality", "score": None, "label": None}
        )
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([run])))
        client = _FakeClient([_CODE_EXAMPLE])

        with patch.object(baseline, "_get", return_value=[]):
            import_baseline(client)

        logged = [call["name"] for call in client.experiments.log_evaluation_calls]
        assert logged == ["passed"]

    def test_missing_dataset_is_reported(self):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        client = _FakeClient([])

        def _raise(dataset):
            raise ValueError("not found")

        client.get_dataset = _raise

        results = import_baseline(client)

        assert results["kuma-database"] == "dataset not found in Phoenix"
