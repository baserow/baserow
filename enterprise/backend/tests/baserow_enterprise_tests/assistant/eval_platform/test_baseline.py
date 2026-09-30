from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest
from phoenix.client import Client

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


@pytest.fixture(autouse=True)
def import_metadata_patch():
    with patch.object(baseline.httpx, "patch") as request:
        yield request


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
        self.records: list[dict] = []

    def list(self, **kwargs):
        return list(self.records)

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        record = {
            "id": f"exp-baseline-{len(self.create_calls)}",
            "name": kwargs["experiment_name"],
            "dataset_version_id": kwargs["dataset_version_id"],
            "metadata": dict(kwargs["experiment_metadata"]),
            "successful_run_count": 0,
        }
        self.records.append(record)
        return record

    def log_run(self, **kwargs):
        self.log_run_calls.append(kwargs)
        next(
            record for record in self.records if record["id"] == kwargs["experiment_id"]
        )["successful_run_count"] += 1
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


@contextmanager
def _sdk_client(handler):
    """Exercise Phoenix's real SDK and the direct requests at their HTTP boundary."""

    with (
        httpx.Client(
            base_url="http://phoenix.test", transport=httpx.MockTransport(handler)
        ) as http,
        patch.object(baseline.httpx, "get", side_effect=http.get),
        patch.object(baseline.httpx, "post", side_effect=http.post),
        patch.object(baseline.httpx, "patch", side_effect=http.patch),
    ):
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments = Client(http_client=http).experiments
        yield client


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
                {
                    "id": "exp-2",
                    "name": "latest",
                    "metadata": {
                        "model": "m",
                        "harness_version": 4,
                        "evaluator_source_hash": "checks-v4",
                    },
                },
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
        client.experiments.records = rest["/v1/datasets/ds-1/experiments"]
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
        assert dataset_entry["metadata"]["harness_version"] == 4
        assert dataset_entry["metadata"]["evaluator_source_hash"] == "checks-v4"
        captured_hash = baseline._snapshot_hash(snapshot)
        dataset_entry["metadata"]["evaluator_source_hash"] = "changed-checks"
        assert baseline._snapshot_hash(snapshot) != captured_hash

    def test_experiment_name_filter_and_missing_experiment(self):
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments.records = [
            {"id": "exp-2", "name": "other", "metadata": {}},
        ]
        results = capture_baseline(client, experiment_name="baseline-candidate")

        assert results["kuma-database"] == "no matching experiment"
        snapshot = json.loads(baseline.BASELINE_PATH.read_text())
        assert snapshot["datasets"] == {}

    @pytest.mark.parametrize("error", ["Provider unavailable", ""])
    def test_errored_run_does_not_replace_snapshot(self, error):
        original = json.dumps(_snapshot([_snapshot_run()]))
        baseline.BASELINE_PATH.write_text(original)
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments.records = [{"id": "exp-1", "name": "candidate"}]
        failed_run = {**_run_payload(), "output": None, "error": error}

        with patch.object(baseline, "_get", return_value=[failed_run]):
            with pytest.raises(ValueError, match="exp-1.*database/list-tables"):
                capture_baseline(client)

        assert baseline.BASELINE_PATH.read_text() == original

    def test_scored_model_failure_can_be_captured(self):
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments.records = [{"id": "exp-1", "name": "candidate"}]
        failed_model_run = {
            **_run_payload(),
            "output": {"passed": False, "score": 0.0},
            "error": None,
        }
        with (
            patch.object(baseline, "_get", return_value=[failed_model_run]),
            patch.object(
                baseline,
                "_run_annotations",
                return_value=[{"name": "passed", "score": 0.0}],
            ),
            patch.object(baseline, "_experiment_totals", return_value={}),
        ):
            capture_baseline(client)

        saved = json.loads(baseline.BASELINE_PATH.read_text())
        run = saved["datasets"]["kuma-database"]["runs"][0]
        assert run["output"] == failed_model_run["output"]
        assert run["annotations"] == [{"name": "passed", "score": 0.0}]


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


def _persist_import_requests(monkeypatch, client, import_metadata_patch):
    """Keep the fake Phoenix state across import attempts and restarts."""

    deleted_ids = []

    def update(url, *, json, **kwargs):
        experiment_id = url.rsplit("/", 1)[-1]
        next(
            record
            for record in client.experiments.records
            if record["id"] == experiment_id
        )["metadata"] = json["metadata"]
        return import_metadata_patch.return_value

    def delete(experiment_ids):
        deleted_ids.extend(experiment_ids)
        client.experiments.records[:] = [
            record
            for record in client.experiments.records
            if record["id"] not in experiment_ids
        ]

    monkeypatch.setattr(baseline, "_delete_experiments", delete)
    import_metadata_patch.side_effect = update
    return deleted_ids


@pytest.mark.parametrize("action", ["capture", "import"])
def test_baseline_finds_experiments_beyond_first_page(action):
    snapshot = _snapshot([_snapshot_run()])
    baseline.BASELINE_PATH.write_text(json.dumps(snapshot))
    recent = [
        {"id": f"live-{i}", "name": f"candidate-{i}", "metadata": {}} for i in range(50)
    ]
    older = [
        {
            "id": "current-import",
            "name": "baseline (imported)",
            "dataset_version_id": "v1",
            "metadata": {
                "baseline_snapshot_hash": baseline._snapshot_hash(snapshot),
                "baseline_import_complete": True,
            },
            "successful_run_count": 1,
        },
        {
            "id": "obsolete-import",
            "name": "baseline (imported)",
            "metadata": {"baseline_snapshot_hash": "previous"},
        },
    ]
    cursors = []
    deleted = []

    def respond(request):
        if request.url.path == "/v1/datasets/ds-1/experiments":
            assert request.method == "GET"
            cursor = request.url.params.get("cursor")
            cursors.append(cursor)
            return httpx.Response(
                200,
                json={
                    "data": older if cursor else recent,
                    "next_cursor": None if cursor else "older",
                },
            )
        if request.url.path == "/v1/experiments/current-import/runs":
            return httpx.Response(200, json={"data": [_run_payload()]})
        if request.url.path == "/graphql":
            body = json.loads(request.content)
            deleted.extend(body["variables"]["ids"])
            return httpx.Response(200, json={"data": {}})
        raise AssertionError((request.method, request.url.path))

    with (
        _sdk_client(respond) as client,
        patch.object(baseline, "_run_annotations", return_value=[]),
        patch.object(baseline, "_experiment_totals", return_value={}),
    ):
        if action == "capture":
            result = capture_baseline(client, experiment_name="baseline (imported)")
            assert (
                result["kuma-database"] == "captured 1 runs from 'baseline (imported)'"
            )
            saved = json.loads(baseline.BASELINE_PATH.read_text())
            assert len(saved["datasets"]["kuma-database"]["runs"]) == 1
            assert deleted == []
        else:
            assert import_baseline(client)["kuma-database"] == "already imported"
            assert deleted == ["obsolete-import"]
    assert cursors == [None, "older"]


class TestImportBaseline:
    def test_no_snapshot_file(self):
        assert import_baseline(_FakeClient([])) == {
            "status": "no baseline snapshot committed"
        }

    def test_imports_runs_and_evaluations_and_skips_removed_cases(
        self, import_metadata_patch
    ):
        baseline.BASELINE_PATH.write_text(
            json.dumps(_snapshot([_snapshot_run(), _snapshot_run("database/gone")]))
        )
        client = _FakeClient([_CODE_EXAMPLE])

        results = import_baseline(client)

        assert results["kuma-database"] == "imported 1 runs (1 removed cases skipped)"
        create = client.experiments.create_calls[0]
        assert create["experiment_name"] == "baseline (imported)"
        assert create["experiment_metadata"]["baseline"] is True
        assert create["experiment_metadata"]["baseline_import_complete"] is False
        assert create["experiment_metadata"]["model"] == "m"
        assert create["experiment_metadata"]["baseline_totals"] == {
            "total_cost": 0.05,
            "total_tokens": 120000,
        }
        assert client.experiments.log_run_calls[0]["dataset_example_id"] == "node-1"
        assert client.experiments.log_evaluation_calls[0]["name"] == "passed"
        assert import_metadata_patch.call_args.args[0].endswith(
            "/v1/experiments/exp-baseline-1"
        )
        assert import_metadata_patch.call_args.kwargs["json"] == {
            "metadata": {
                **create["experiment_metadata"],
                "baseline_import_complete": True,
            }
        }
        import_metadata_patch.return_value.raise_for_status.assert_called_once_with()

    def test_import_replaces_only_owned_experiments_regardless_of_name(self):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        client = _FakeClient([_CODE_EXAMPLE])
        existing = [
            {
                "id": "exp-old-baseline",
                "name": "baseline",
                "metadata": {"baseline_snapshot_hash": "oldhash123456"},
                "successful_run_count": 1,
            },
            {
                "id": "renamed-import",
                "name": "old saved import",
                "metadata": {"baseline_snapshot_hash": "olderhash"},
            },
            {"id": "live-baseline", "name": "baseline", "metadata": {}},
            {
                "id": "live-import-name",
                "name": "baseline (imported)",
                "metadata": {},
            },
        ]

        with (
            patch.object(client.experiments, "list", return_value=existing),
            patch.object(baseline, "_delete_experiments") as mock_delete,
        ):
            results = import_baseline(client)

        mock_delete.assert_called_once_with(["exp-old-baseline", "renamed-import"])
        assert results["kuma-database"] == "imported 1 runs"

    def test_import_is_idempotent_by_snapshot_hash(self):
        snapshot = _snapshot([_snapshot_run()])
        baseline.BASELINE_PATH.write_text(json.dumps(snapshot))
        content_hash = baseline._snapshot_hash(snapshot)
        client = _FakeClient([_CODE_EXAMPLE])
        existing = [
            {
                "id": "current-import",
                "name": "baseline (imported)",
                "dataset_version_id": "v1",
                "metadata": {
                    "baseline_snapshot_hash": content_hash,
                    "baseline_import_complete": True,
                },
                "successful_run_count": 1,
            }
        ]

        with patch.object(client.experiments, "list", return_value=existing):
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
                "id": "incomplete-import",
                "name": "baseline (imported)",
                "dataset_version_id": "v1",
                "metadata": {
                    "baseline_snapshot_hash": content_hash,
                    "baseline_import_complete": False,
                },
                "successful_run_count": 0,
            }
        ]

        with (
            patch.object(client.experiments, "list", return_value=existing),
            patch.object(baseline, "_delete_experiments") as mock_delete,
        ):
            results = import_baseline(client)

        assert results["kuma-database"] == "imported 1 runs"
        assert len(client.experiments.create_calls) == 1
        mock_delete.assert_called_once_with(["incomplete-import"])

    def test_removed_cases_do_not_repeat_import_or_replace_a_live_baseline(
        self, monkeypatch, import_metadata_patch
    ):
        baseline.BASELINE_PATH.write_text(
            json.dumps(_snapshot([_snapshot_run(), _snapshot_run("database/gone")]))
        )
        client = _FakeClient([_CODE_EXAMPLE])
        live = {"id": "live-baseline", "name": "baseline", "metadata": {}}
        client.experiments.records.append(live)
        deleted = _persist_import_requests(monkeypatch, client, import_metadata_patch)

        first = import_baseline(client)
        second = import_baseline(client)

        assert first["kuma-database"] == "imported 1 runs (1 removed cases skipped)"
        assert second["kuma-database"] == "already imported"
        assert len(client.experiments.create_calls) == 1
        assert deleted == []
        assert [record["name"] for record in client.experiments.records] == [
            "baseline",
            "baseline (imported)",
        ]
        assert client.experiments.records[0] == live

    @pytest.mark.parametrize(
        "name, version, complete",
        [("baseline", "v1", None), ("baseline (imported)", "old-version", True)],
        ids=("legacy-name", "changed-dataset-version"),
    )
    def test_replaces_legacy_or_outdated_import_even_with_matching_snapshot_hash(
        self, monkeypatch, import_metadata_patch, name, version, complete
    ):
        snapshot = _snapshot([_snapshot_run()])
        baseline.BASELINE_PATH.write_text(json.dumps(snapshot))
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments.records.append(
            {
                "id": "previous-import",
                "name": name,
                "dataset_version_id": version,
                "metadata": {
                    "baseline_snapshot_hash": baseline._snapshot_hash(snapshot),
                    "baseline_import_complete": complete,
                },
                "successful_run_count": 1,
            }
        )
        deleted = _persist_import_requests(monkeypatch, client, import_metadata_patch)

        result = import_baseline(client)

        assert result["kuma-database"] == "imported 1 runs"
        assert deleted == ["previous-import"]
        assert client.experiments.records[0]["name"] == "baseline (imported)"
        assert client.experiments.records[0]["dataset_version_id"] == "v1"

    @pytest.mark.parametrize(
        "failure_path, status, cleanup_fails",
        [
            ("/runs", 409, False),
            ("/v1/experiment_evaluations", 503, False),
            ("completion", 503, False),
            ("completion", 503, True),
        ],
        ids=("run-conflict", "annotation", "completion", "cleanup-also-fails"),
    )
    def test_failed_import_preserves_old_results_and_can_retry(
        self, failure_path, status, cleanup_fails
    ):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        previous = {
            "live-baseline": {
                "id": "live-baseline",
                "name": "baseline",
                "metadata": {},
            },
            "previous-import": {
                "id": "previous-import",
                "name": "baseline (imported)",
                "metadata": {"baseline_snapshot_hash": "previous-snapshot"},
            },
        }
        records = dict(previous)
        created = 0
        fail = True

        def respond(request):
            nonlocal created
            path = request.url.path
            body = json.loads(request.content) if request.content else {}
            if path == "/v1/datasets/ds-1/experiments":
                if request.method == "GET":
                    return httpx.Response(200, json={"data": list(records.values())})
                created += 1
                record = {
                    "id": f"new-{created}",
                    "name": body["name"],
                    "dataset_version_id": body["version_id"],
                    "metadata": body["metadata"],
                    "successful_run_count": 0,
                }
                records[record["id"]] = record
                return httpx.Response(200, json={"data": record})
            if request.method == "DELETE":
                experiment_id = path.rsplit("/", 1)[-1]
                assert experiment_id.startswith("new-")
                if cleanup_fails:
                    return httpx.Response(502, json={"detail": "cleanup unavailable"})
                del records[experiment_id]
                return httpx.Response(204)
            if fail and (
                path.endswith(failure_path)
                or (failure_path == "completion" and request.method == "PATCH")
            ):
                return httpx.Response(status, json={"detail": "original failure"})
            if path.endswith("/runs"):
                records[path.split("/")[3]]["successful_run_count"] += 1
                return httpx.Response(200, json={"data": {"id": "run-1"}})
            if path == "/v1/experiment_evaluations":
                return httpx.Response(200, json={"data": {"id": "evaluation-1"}})
            if request.method == "PATCH":
                records[path.rsplit("/", 1)[-1]]["metadata"] = body["metadata"]
                return httpx.Response(200, json={"data": {}})
            if path == "/graphql":
                for experiment_id in body["variables"]["ids"]:
                    del records[experiment_id]
                return httpx.Response(200, json={"data": {}})
            raise AssertionError((request.method, path))

        with (
            _sdk_client(respond) as client,
            patch.object(baseline.logger, "warning") as warning,
        ):
            for _ in range(1 if cleanup_fails else 2):
                with pytest.raises(httpx.HTTPStatusError) as caught:
                    import_baseline(client)
                assert caught.value.response.status_code == status
                assert caught.value.response.json()["detail"] == "original failure"
                assert {key: records[key] for key in previous} == previous
                if not cleanup_fails:
                    assert records == previous
            if cleanup_fails:
                warning.assert_called_once()
                assert (
                    "Could not delete failed baseline import"
                    in warning.call_args.args[0]
                )

            fail = False
            cleanup_fails = False
            assert import_baseline(client)["kuma-database"] == "imported 1 runs"
            assert set(records) == {"live-baseline", f"new-{created}"}
            assert records[f"new-{created}"]["metadata"]["baseline_import_complete"]
            assert import_baseline(client)["kuma-database"] == "already imported"

    def test_retries_cleanup_without_reimporting_completed_results(
        self, monkeypatch, import_metadata_patch
    ):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        client = _FakeClient([_CODE_EXAMPLE])
        client.experiments.records.append(
            {
                "id": "previous-import",
                "name": "baseline",
                "metadata": {"baseline_snapshot_hash": "previous-snapshot"},
            }
        )
        deleted = _persist_import_requests(monkeypatch, client, import_metadata_patch)

        with patch.object(
            baseline, "_delete_experiments", side_effect=RuntimeError("unavailable")
        ):
            first = import_baseline(client)
        second = import_baseline(client)

        assert first["kuma-database"] == "imported 1 runs"
        assert second["kuma-database"] == "already imported"
        assert len(client.experiments.create_calls) == 1
        assert deleted == ["previous-import"]

    def test_no_applicable_cases_preserve_existing_experiments(self):
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([_snapshot_run()])))
        client = _FakeClient([])

        with (
            patch.object(client.experiments, "list") as mock_list,
            patch.object(baseline, "_delete_experiments") as mock_delete,
        ):
            first = import_baseline(client)
            second = import_baseline(client)

        assert (
            first
            == second
            == {"kuma-database": "no snapshot cases in the current dataset"}
        )
        assert client.experiments.create_calls == []
        mock_list.assert_not_called()
        mock_delete.assert_not_called()

    def test_import_drops_no_result_annotations(self):
        run = _snapshot_run()
        run["annotations"].append(
            {"name": "answer_quality", "score": None, "label": None}
        )
        baseline.BASELINE_PATH.write_text(json.dumps(_snapshot([run])))
        client = _FakeClient([_CODE_EXAMPLE])

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


class TestDumpSnapshot:
    def test_round_trips_and_keeps_each_run_on_one_line(self):
        """The one-line-per-run format caps the committed file's line count
        (a pretty-printed snapshot is ~20k diff lines) without losing data."""

        snapshot = {
            "captured_at": "2026-09-02T00:00:00+00:00",
            "datasets": {
                "kuma-core": {
                    "experiment_name": "run-x",
                    "metadata": {"model": "m"},
                    "totals": {"total_cost": 1.5},
                    "runs": [
                        {"case_id": "core/a", "output": {"answer": "hi\nthere"}},
                        {"case_id": "core/b", "output": {}},
                    ],
                },
                "kuma-docs": {
                    "experiment_name": None,
                    "metadata": {},
                    "totals": {},
                    "runs": [],
                },
            },
        }

        text = baseline._dump_snapshot(snapshot)

        assert json.loads(text) == snapshot
        run_lines = [line for line in text.splitlines() if '"case_id"' in line]
        assert len(run_lines) == 2
