from __future__ import annotations

import io
import json
import queue as queue_module
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from django.core.management import call_command

import pytest

from baserow_enterprise.assistant.evals import registry, runner
from baserow_enterprise.assistant.evals.types import EvalCase
from baserow_enterprise.management.commands import (
    assistant_eval_runner as eval_runner_command,
)


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


@pytest.fixture(autouse=True)
def _isolated_runner_state(monkeypatch):
    monkeypatch.setattr(runner, "_history", runner.deque(maxlen=runner.MAX_HISTORY))
    monkeypatch.setattr(runner, "_run_queue", queue_module.Queue())
    monkeypatch.setattr(runner, "_worker_started", False)
    monkeypatch.setattr(runner, "_phoenix_client", None)
    monkeypatch.setattr(runner, "_dataset_links", {})
    monkeypatch.setattr(runner, "_dataset_ids", {})
    monkeypatch.setattr(runner, "_ui_cases", {})
    monkeypatch.setattr(runner, "_active_run", None)


def _noop_checks(case, scenario, output):
    return []


def _register_case(case_id: str, dataset: str = "kuma-database") -> EvalCase:
    case = EvalCase(
        id=case_id,
        dataset=dataset,
        prompt="do the thing",
        scenario="empty-workspace",
        checks=_noop_checks,
    )
    registry.register_case(case)
    return case


def _call_wsgi(
    app,
    method: str,
    path: str,
    body: bytes = b"",
    content_type: str = "application/x-www-form-urlencoded",
    extra_environ: dict | None = None,
):
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    environ.update(extra_environ or {})
    if body:
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["CONTENT_TYPE"] = content_type
        environ["wsgi.input"] = io.BytesIO(body)

    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    result = app(environ, start_response)
    body_bytes = b"".join(result)
    return captured["status"], captured["headers"], body_bytes


class TestIndexPage:
    def test_get_index_returns_200_and_lists_registered_dataset(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        status, _headers, body = _call_wsgi(app, "GET", "/")

        assert status == "200 OK"
        assert b"kuma-database" in body
        assert b"database/list-tables" in body

    def test_get_index_shows_recent_runs(self):
        _register_case("database/list-tables")
        runner.submit_run(dataset="kuma-database", model="groq:test-model")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b"queued" in body

    def test_index_deep_links_finished_run_when_experiment_info_has_ids(
        self, settings, monkeypatch
    ):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://phoenix:6006"
        monkeypatch.setenv(
            "BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL", "http://localhost:6060"
        )
        _register_case("database/list-tables")
        state = runner.submit_run(dataset="kuma-database", model="m")
        stub = MagicMock(
            return_value={
                "dataset_id": "RGF0YXNldDoz",
                "experiment_id": "RXhwZXJpbWVudDoz",
            }
        )
        runner._run_one(state, stub)
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert (
            b'href="http://localhost:6060/datasets/RGF0YXNldDoz/'
            b'compare?experimentId=RXhwZXJpbWVudDoz"' in body
        )
        assert b"http://phoenix:6006" not in body

    def test_index_falls_back_to_datasets_list_without_experiment_ids(
        self, settings, monkeypatch
    ):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://phoenix:6006"
        monkeypatch.setenv(
            "BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL", "http://localhost:6060"
        )
        _register_case("database/list-tables")
        state = runner.submit_run(dataset="kuma-database", model="m")
        runner._run_one(state, MagicMock(return_value={"unrelated": "shape"}))
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b'href="http://localhost:6060/datasets"' in body

    def test_index_link_falls_back_to_settings_url_when_public_url_env_unset(
        self, settings, monkeypatch
    ):
        settings.BASEROW_ASSISTANT_PHOENIX_URL = "http://phoenix-fallback:6006"
        monkeypatch.delenv("BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL", raising=False)
        _register_case("database/list-tables")
        state = runner.submit_run(dataset="kuma-database", model="m")
        runner._run_one(state, MagicMock(return_value={}))
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b'href="http://phoenix-fallback:6006/datasets"' in body


class TestGitLabelOnSubmit:
    def test_submit_run_captures_branch_and_commit(self, monkeypatch):
        monkeypatch.setattr(
            runner,
            "get_git_info",
            lambda: {"git_branch": "feature/x", "git_commit": "abc1234"},
        )

        state = runner.submit_run(dataset="kuma-database", model="m")

        assert state.git_label == "feature/x@abc1234"

    def test_submit_run_uses_whichever_single_value_resolved(self, monkeypatch):
        monkeypatch.setattr(runner, "get_git_info", lambda: {"git_branch": "feature/x"})

        state = runner.submit_run(dataset="kuma-database", model="m")

        assert state.git_label == "feature/x"

    def test_submit_run_git_label_none_when_unresolved(self, monkeypatch):
        monkeypatch.setattr(runner, "get_git_info", lambda: {})

        state = runner.submit_run(dataset="kuma-database", model="m")

        assert state.git_label is None

    def test_index_shows_git_label_next_to_model(self, monkeypatch):
        monkeypatch.setattr(
            runner,
            "get_git_info",
            lambda: {"git_branch": "feature/x", "git_commit": "abc1234"},
        )
        _register_case("database/list-tables")
        runner.submit_run(dataset="kuma-database", model="groq:test-model")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b"groq:test-model" in body
        assert b"feature/x@abc1234" in body


class TestHealthz:
    def test_healthz_returns_200(self):
        app = runner.make_wsgi_app()

        status, _headers, _body = _call_wsgi(app, "GET", "/healthz")

        assert status == "200 OK"


class TestUiExampleSupport:
    def test_ui_ids_group_by_their_encoded_dataset(self):
        _register_case("database/list-tables")

        grouped = runner._group_case_ids_by_dataset(
            ["ui:kuma-docs:ex-1", "database/list-tables", "ui:kuma-database:ex-2"]
        )

        assert grouped == {
            "kuma-docs": ["ui:kuma-docs:ex-1"],
            "kuma-database": ["database/list-tables", "ui:kuma-database:ex-2"],
        }

    def test_index_lists_ui_cases_for_their_dataset(self, monkeypatch):
        _register_case("database/list-tables")
        monkeypatch.setattr(
            runner,
            "_ui_cases",
            {
                "kuma-database": [
                    {"value": "ui:kuma-database:ex-1", "label": "create a Tasks table"}
                ]
            },
        )
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b"Added in the Phoenix UI" in body
        assert b'value="ui:kuma-database:ex-1"' in body
        assert b"create a Tasks table" in body

    def test_refresh_dataset_state_collects_links_and_ui_examples(self, monkeypatch):
        _register_case("database/list-tables")
        monkeypatch.setenv(
            "BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL", "http://localhost:6060"
        )
        monkeypatch.setattr(runner, "_dataset_links", {})
        monkeypatch.setattr(runner, "_ui_cases", {})
        monkeypatch.setattr(runner, "_phoenix_client", None)
        dataset = MagicMock(id="ds-1")
        dataset.examples = [
            {
                "id": "code-1",
                "input": {"prompt": "p"},
                "metadata": {"case_id": "database/list-tables"},
            },
            {"id": "ex-1", "input": {"prompt": "try something new"}, "metadata": {}},
        ]
        client = MagicMock()
        client.datasets.get_dataset.return_value = dataset

        runner.refresh_dataset_state(client)

        assert runner._dataset_links == {
            "kuma-database": "http://localhost:6060/datasets/ds-1/examples"
        }
        assert runner._ui_cases["kuma-database"] == [
            {"value": "ui:kuma-database:ex-1", "label": "try something new"}
        ]

    def test_index_rerefreshes_state_when_a_client_is_known(self, monkeypatch):
        _register_case("database/list-tables")
        refreshed = []
        monkeypatch.setattr(runner, "_phoenix_client", object())
        monkeypatch.setattr(
            runner, "refresh_dataset_state", lambda client: refreshed.append(client)
        )
        app = runner.make_wsgi_app()

        _call_wsgi(app, "GET", "/")

        assert len(refreshed) == 1


class TestResultsEndpoint:
    def test_results_json_aggregates_experiment_summaries(self, monkeypatch):
        _register_case("database/list-tables")
        monkeypatch.setattr(runner, "_dataset_ids", {"kuma-database": "ds-node-1"})
        monkeypatch.setenv(
            "BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL", "http://localhost:6060"
        )
        summaries = [
            {
                "id": "exp-1",
                "name": "baseline",
                "createdAt": "2026-08-25T10:00:00Z",
                "metadata": {"model": "m", "git_branch": "b", "git_commit": "c"},
                "repetitions": 2,
                "runCount": 2,
                "expectedRunCount": 2,
                "averageRunLatencyMs": 6000.0,
                "costSummary": {"total": {"cost": 0.05, "tokens": 120000}},
                "annotationSummaries": [
                    {
                        "annotationName": "checklist",
                        "meanScore": 0.9,
                        "scoreCount": 2,
                    },
                    {
                        "annotationName": "passed",
                        "meanScore": 0.8,
                        "scoreCount": 2,
                    },
                    {
                        "annotationName": "answer_quality",
                        "meanScore": None,
                        "scoreCount": 0,
                    },
                ],
            }
        ]
        monkeypatch.setattr(runner, "_experiment_summaries", lambda node_id: summaries)
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/results.json")

        dataset = json.loads(body)["datasets"][0]
        assert dataset["name"] == "kuma-database"
        assert dataset["case_count"] == 1
        experiment = dataset["experiments"][0]
        assert experiment["scores"] == {"checklist": 0.9, "passed": 0.8}
        assert experiment["run_count"] == 2
        assert experiment["expected_run_count"] == 2
        assert experiment["repetitions"] == 2
        assert experiment["scored_run_count"] == 2
        assert experiment["score_counts"] == {
            "checklist": 2,
            "passed": 2,
            "answer_quality": 0,
        }
        assert experiment["complete"] is True
        assert experiment["git_label"] == "b@c"
        assert experiment["time_s"] == 12.0
        assert experiment["cost"] == 0.05
        assert experiment["tokens"] == 120000
        assert experiment["link"] == (
            "http://localhost:6060/datasets/ds-node-1/compare?experimentId=exp-1"
        )

    @pytest.mark.parametrize(
        ("score_counts", "scored_run_count"),
        [
            ({"checklist": 1, "passed": 2}, 1),
            ({"checklist": 2, "passed": 1}, 1),
            ({"checklist": 0, "passed": 0}, 0),
        ],
        ids=("partial-checklist", "partial-passed", "all-skipped"),
    )
    def test_results_json_marks_incomplete_without_all_mandatory_scores(
        self, monkeypatch, score_counts, scored_run_count
    ):
        _register_case("database/list-tables")
        monkeypatch.setattr(runner, "_dataset_ids", {"kuma-database": "ds-node-1"})
        summaries = [
            {
                "id": "exp-1",
                "name": "candidate",
                "runCount": 2,
                "expectedRunCount": 2,
                "annotationSummaries": [
                    {
                        "annotationName": name,
                        "meanScore": 1.0 if count else None,
                        "scoreCount": count,
                    }
                    for name, count in score_counts.items()
                ],
            }
        ]
        monkeypatch.setattr(runner, "_experiment_summaries", lambda node_id: summaries)
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/results.json")

        experiment = json.loads(body)["datasets"][0]["experiments"][0]
        assert experiment["run_count"] == 2
        assert experiment["expected_run_count"] == 2
        assert experiment["scored_run_count"] == scored_run_count
        assert experiment["score_counts"] == score_counts
        assert experiment["complete"] is False

    def test_results_summary_query_requests_completeness_counts(self):
        assert "expectedRunCount" in runner._EXPERIMENT_SUMMARIES_QUERY
        assert "scoreCount" in runner._EXPERIMENT_SUMMARIES_QUERY

    def test_results_json_falls_back_to_frozen_baseline_totals(self, monkeypatch):
        _register_case("database/list-tables")
        monkeypatch.setattr(runner, "_dataset_ids", {"kuma-database": "ds-node-1"})
        summaries = [
            {
                "id": "exp-1",
                "name": "baseline",
                "createdAt": "2026-08-25T10:00:00Z",
                "metadata": {
                    "baseline_totals": {
                        "run_count": 2,
                        "average_run_latency_ms": 3000.0,
                        "total_cost": 0.02,
                        "total_tokens": 50000,
                    }
                },
                "runCount": 2,
                "averageRunLatencyMs": None,
                "costSummary": {"total": {"cost": None, "tokens": None}},
                "annotationSummaries": [],
            }
        ]
        monkeypatch.setattr(runner, "_experiment_summaries", lambda node_id: summaries)
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/results.json")

        experiment = json.loads(body)["datasets"][0]["experiments"][0]
        assert experiment["time_s"] == 6.0
        assert experiment["cost"] == 0.02
        assert experiment["tokens"] == 50000

    def test_results_json_is_empty_without_known_dataset_ids(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/results.json")

        assert json.loads(body)["datasets"][0]["experiments"] == []

    def test_index_has_results_tab(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b'data-tab="__results"' in body

    def test_results_tab_compares_across_repetition_counts(self):
        """A --runs 3 experiment must still show deltas against a 1-pass
        baseline: means compare directly, totals are divided by repetitions."""

        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        page = body.decode("utf-8")
        assert (
            "experiment.expected_run_count === baseline.expected_run_count" not in page
        )
        assert (
            "var comparable = experimentComplete && baseline && baseline.complete;"
            in page
        )
        assert "candidate.repetitions" in page
        assert 'perPass(experiment, "time_s")' in page
        assert 'perPass(baseline, "cost")' in page
        assert "time and cost shown per pass" in page

    def test_results_tab_requires_full_metric_coverage_on_both_sides(self):
        """answer_quality only compares when the judge scored every run in both
        the experiment and the baseline, not merely the same number of runs."""

        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        page = body.decode("utf-8")
        assert (
            "experiment.score_counts[metric] === experiment.expected_run_count" in page
        )
        assert "baseline.score_counts[metric] === baseline.expected_run_count" in page
        assert (
            "experiment.score_counts[metric] === baseline.score_counts[metric]"
            not in page
        )


class TestDocsEndpoint:
    def test_docs_json_serves_the_help_docs(self):
        app = runner.make_wsgi_app()

        status, headers, body = _call_wsgi(app, "GET", "/docs.json")

        assert status == "200 OK"
        assert headers["Content-Type"] == "application/json"
        docs = json.loads(body)["docs"]
        assert [doc["slug"] for doc in docs] == ["evals", "analysis", "tracing"]
        assert "# AI Assistant Evals" in docs[0]["markdown"]
        assert "baseline" in docs[1]["markdown"]
        assert docs[2]["path"] == "docs/development/ai-assistant-tracing.md"

    def test_docs_json_degrades_to_empty_markdown_when_files_missing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(runner, "_repo_root", lambda: tmp_path)
        app = runner.make_wsgi_app()

        status, _headers, body = _call_wsgi(app, "GET", "/docs.json")

        assert status == "200 OK"
        assert all(doc["markdown"] == "" for doc in json.loads(body)["docs"])

    def test_index_page_has_help_tab(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b'data-tab="__help"' in body


class TestSubmitRunRoute:
    def test_post_run_enqueues_and_redirects(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode(
            {"dataset": "kuma-database", "model": "groq:test-model", "runs": "1"}
        ).encode()

        status, headers, _body = _call_wsgi(app, "POST", "/run", body=body)

        assert status == "303 See Other"
        assert headers["Location"] == "/"
        history = runner.recent_runs()
        assert len(history) == 1
        assert history[0].dataset == "kuma-database"
        assert history[0].model == "groq:test-model"
        assert history[0].status == "queued"

    @pytest.fixture(autouse=True)
    def _isolated_history_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner, "_HISTORY_FILE", str(tmp_path / "history.json"))

    def test_history_survives_restart_and_marks_inflight_interrupted(self):
        _register_case("database/persist-a")
        done = runner.submit_run(dataset="kuma-database", model="groq:test-model")
        done.status = "done"
        done.phoenix_link = "http://localhost:6060/datasets/x"
        running = runner.submit_run(dataset="kuma-core", model="groq:test-model")
        running.status = "running"
        runner._save_history()

        with runner._history_lock:
            runner._history.clear()
        runner.load_history()

        by_id = {state.id: state for state in runner.recent_runs()}
        assert by_id[done.id].status == "done"
        assert by_id[done.id].phoenix_link == "http://localhost:6060/datasets/x"
        assert by_id[running.id].status == "failed"
        assert by_id[running.id].error == "interrupted by runner restart"

    def test_cross_dataset_selection_fans_out_one_run_per_dataset(self):
        _register_case("database/fanout-a")
        _register_case("core/fanout-b", dataset="kuma-core")
        app = runner.make_wsgi_app()
        body = urlencode(
            {"dataset": "kuma-database", "model": "groq:test-model", "runs": "1"},
        ).encode()
        body += b"&case_ids=database%2Ffanout-a&case_ids=core%2Ffanout-b"

        status, _headers, _body = _call_wsgi(app, "POST", "/run", body=body)

        assert status == "303 See Other"
        history = runner.recent_runs()
        assert {(run.dataset, tuple(run.case_ids)) for run in history} == {
            ("kuma-core", ("core/fanout-b",)),
            ("kuma-database", ("database/fanout-a",)),
        }

    def test_post_run_collects_repeated_case_ids(self):
        _register_case("database/list-tables")
        _register_case("database/create-table")
        app = runner.make_wsgi_app()
        body = urlencode(
            {
                "dataset": "kuma-database",
                "model": "groq:test-model",
                "runs": "2",
                "case_ids": ["database/list-tables", "database/create-table"],
            },
            doseq=True,
        ).encode()

        _call_wsgi(app, "POST", "/run", body=body)

        history = runner.recent_runs()
        assert history[0].case_ids == [
            "database/list-tables",
            "database/create-table",
        ]
        assert history[0].runs == 2

    def test_post_run_uses_free_text_model_override(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode(
            {
                "dataset": "kuma-database",
                "model": "groq:test-model",
                "model_custom": "openai:custom-model",
            }
        ).encode()

        _call_wsgi(app, "POST", "/run", body=body)

        assert runner.recent_runs()[0].model == "openai:custom-model"

    def test_post_run_with_oversized_content_length_returns_413_without_reading_body(
        self,
    ):
        app = runner.make_wsgi_app()
        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "POST"
        environ["PATH_INFO"] = "/run"
        environ["CONTENT_LENGTH"] = str(runner.MAX_FORM_BYTES + 1)
        environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"

        class _ExplodingStream:
            def read(self, *args, **kwargs):
                raise AssertionError("must not read an oversized body")

        environ["wsgi.input"] = _ExplodingStream()
        captured: dict = {}

        def start_response(status, headers):
            captured["status"] = status

        result = app(environ, start_response)
        b"".join(result)

        assert captured["status"] == "413 Payload Too Large"
        assert runner.recent_runs() == []

    def test_post_run_with_non_utf8_body_returns_400(self):
        app = runner.make_wsgi_app()
        body = b"dataset=kuma-database&model=\xff\xfe"

        status, _headers, _body = _call_wsgi(app, "POST", "/run", body=body)

        assert status == "400 Bad Request"
        assert runner.recent_runs() == []

    def test_post_run_rejects_forged_origin(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode({"dataset": "kuma-database", "model": "m"}).encode()

        status, _headers, _body = _call_wsgi(
            app,
            "POST",
            "/run",
            body=body,
            extra_environ={"HTTP_ORIGIN": "http://evil.example.com"},
        )

        assert status == "403 Forbidden"
        assert runner.recent_runs() == []

    def test_post_run_rejects_non_loopback_host(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode({"dataset": "kuma-database", "model": "m"}).encode()

        status, _headers, _body = _call_wsgi(
            app,
            "POST",
            "/run",
            body=body,
            extra_environ={"HTTP_HOST": "evil.example.com"},
        )

        assert status == "403 Forbidden"
        assert runner.recent_runs() == []

    def test_post_run_allows_loopback_origin_with_port(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode({"dataset": "kuma-database", "model": "m"}).encode()

        status, _headers, _body = _call_wsgi(
            app,
            "POST",
            "/run",
            body=body,
            extra_environ={
                "HTTP_HOST": "localhost:8090",
                "HTTP_ORIGIN": "http://localhost:8090",
            },
        )

        assert status == "303 See Other"
        assert len(runner.recent_runs()) == 1


class TestSubmitRunWorker:
    def test_state_transitions_to_done_with_stubbed_executor(self):
        stub = MagicMock(return_value={"experiment_id": "exp-1"})
        runner.start_worker(executor=stub)

        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        runner._run_queue.join()

        assert state.status == "done"
        assert state.experiment_info == {"experiment_id": "exp-1"}
        assert state.started_at is not None
        assert state.finished_at is not None
        stub.assert_called_once_with(
            dataset_name="kuma-database",
            model="m",
            case_ids=None,
            runs=1,
            experiment_name=None,
            prompt_overrides=None,
            notes=None,
            control=state.control,
        )

    def test_state_transitions_to_failed_on_exception(self):
        stub = MagicMock(side_effect=RuntimeError("boom"))
        runner.start_worker(executor=stub)

        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        runner._run_queue.join()

        assert state.status == "failed"
        assert state.error == "boom"

    def test_start_worker_is_idempotent(self):
        first = MagicMock(return_value={})
        second = MagicMock(return_value={})
        runner.start_worker(executor=first)
        runner.start_worker(executor=second)

        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        runner._run_queue.join()

        first.assert_called_once()
        second.assert_not_called()
        assert state.status == "done"


class TestKnowledgeBaseStartup:
    def test_syncs_a_capable_empty_knowledge_base(self):
        handler = MagicMock()
        handler.can_have_knowledge_base.return_value = True
        handler.can_search.return_value = False

        with patch.object(
            eval_runner_command, "KnowledgeBaseHandler", return_value=handler
        ):
            eval_runner_command.sync_knowledge_base_if_needed()

        handler.sync_knowledge_base.assert_called_once_with()

    def test_does_not_sync_an_already_searchable_knowledge_base(self):
        handler = MagicMock()
        handler.can_have_knowledge_base.return_value = True
        handler.can_search.return_value = True

        with patch.object(
            eval_runner_command, "KnowledgeBaseHandler", return_value=handler
        ):
            eval_runner_command.sync_knowledge_base_if_needed()

        handler.sync_knowledge_base.assert_not_called()


@pytest.mark.django_db
class TestAssistantEvalRunnerCommand:
    @pytest.fixture(autouse=True)
    def _no_baseline_import(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "import_baseline"
            ) as mock_import,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_knowledge_base_if_needed"
            ) as mock_sync_knowledge_base,
        ):
            self.mock_import_baseline = mock_import
            self.mock_sync_knowledge_base = mock_sync_knowledge_base
            yield

    def test_startup_imports_the_baseline(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ) as mock_get_client,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()

            call_command("assistant_eval_runner", "--skip-migrate")

        self.mock_import_baseline.assert_called_once_with(mock_get_client.return_value)

    def test_skip_migrate_calls_sync_and_starts_server(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ) as mock_call_command,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ) as mock_setup,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ) as mock_load_all,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ) as mock_get_client,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ) as mock_sync,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ) as mock_sync_prompts,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ) as mock_start_worker,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_server = MagicMock()
            mock_make_server.return_value = mock_server

            call_command("assistant_eval_runner", "--skip-migrate")

        mock_call_command.assert_not_called()
        mock_setup.assert_called_once()
        mock_load_all.assert_called_once()
        mock_sync.assert_called_once_with(mock_get_client.return_value)
        mock_sync_prompts.assert_called_once_with(mock_get_client.return_value)
        self.mock_sync_knowledge_base.assert_called_once_with()
        mock_start_worker.assert_called_once()
        mock_make_server.assert_called_once()
        assert mock_make_server.call_args[0][0] == "127.0.0.1"
        mock_server.serve_forever.assert_called_once()

    def test_migrates_unless_skipped(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ) as mock_call_command,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()

            call_command("assistant_eval_runner")

        mock_call_command.assert_called_once_with(
            "migrate", interactive=False, verbosity=0
        )

    def test_sync_failure_is_logged_and_does_not_raise(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets",
                side_effect=RuntimeError("phoenix unreachable"),
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ) as mock_start_worker,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()

            call_command("assistant_eval_runner", "--skip-migrate")

        mock_start_worker.assert_called_once()

    def test_prompt_sync_failure_is_logged_and_does_not_raise(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts",
                side_effect=RuntimeError("phoenix unreachable"),
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ) as mock_start_worker,
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()

            call_command("assistant_eval_runner", "--skip-migrate")

        mock_start_worker.assert_called_once()

    def test_port_defaults_to_env_var(self, monkeypatch):
        monkeypatch.setenv("BASEROW_EVAL_RUNNER_PORT", "9123")
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()

            call_command("assistant_eval_runner", "--skip-migrate")

        assert mock_make_server.call_args[0][1] == 9123

    def test_host_can_be_opened_up_explicitly(self):
        with (
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "call_command"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "setup_instrumentation"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_datasets"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "sync_prompts"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "start_worker"
            ),
            patch(
                "baserow_enterprise.management.commands.assistant_eval_runner."
                "make_server"
            ) as mock_make_server,
        ):
            mock_make_server.return_value = MagicMock()
            bind_all = "0.0.0.0"  # noqa: S104

            call_command("assistant_eval_runner", "--skip-migrate", "--host", bind_all)

        assert mock_make_server.call_args[0][0] == bind_all


class TestPromptOverridesForm:
    def test_post_run_passes_valid_prompt_overrides_and_filters_unknown(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()
        body = urlencode(
            {
                "dataset": "kuma-database",
                "model": "m",
                "prompt_overrides": ["kuma-system-prompt", "not-a-prompt"],
            },
            doseq=True,
        ).encode()

        _call_wsgi(app, "POST", "/run", body=body)

        assert runner.recent_runs()[0].prompt_overrides == ["kuma-system-prompt"]

    def test_runs_json_includes_prompt_overrides(self):
        _register_case("database/list-tables")
        runner.submit_run(
            dataset="kuma-database",
            model="m",
            prompt_overrides=["kuma-system-prompt"],
        )
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/runs.json")

        assert json.loads(body)["runs"][0]["prompt_overrides"] == ["kuma-system-prompt"]

    def test_index_renders_prompt_override_checkboxes(self):
        _register_case("database/list-tables")
        app = runner.make_wsgi_app()

        _status, _headers, body = _call_wsgi(app, "GET", "/")

        assert b'value="kuma-system-prompt"' in body
        assert b"Prompt overrides" in body


class TestSharedExperimentName:
    def test_fan_out_across_datasets_shares_one_generated_name(self):
        _register_case("database/case-1", dataset="kuma-database")
        _register_case("core/case-1", dataset="kuma-core")

        states = runner._submit_from_form(
            {"case_ids": ["database/case-1", "core/case-1"]}
        )

        assert len(states) == 2
        assert states[0].dataset != states[1].dataset
        names = {state.experiment_name for state in states}
        assert len(names) == 1, "the Results tab groups experiments by name"
        assert names.pop().startswith("run-")

    def test_a_typed_name_is_used_verbatim_for_every_dataset(self):
        _register_case("database/case-1", dataset="kuma-database")
        _register_case("core/case-1", dataset="kuma-core")

        states = runner._submit_from_form(
            {
                "case_ids": ["database/case-1", "core/case-1"],
                "experiment_name": ["pr-1234"],
            }
        )

        assert [state.experiment_name for state in states] == ["pr-1234", "pr-1234"]

    def test_separate_submissions_get_separate_names(self):
        _register_case("database/case-1", dataset="kuma-database")

        first = runner._submit_from_form({"case_ids": ["database/case-1"]})
        second = runner._submit_from_form({"case_ids": ["database/case-1"]})

        assert first[0].experiment_name != second[0].experiment_name


class TestCustomModelChoice:
    def test_the_custom_sentinel_never_reaches_the_executor(self):
        _register_case("database/case-1")

        states = runner._submit_from_form(
            {"case_ids": ["database/case-1"], "model": [runner.CUSTOM_MODEL_CHOICE]}
        )

        assert states[0].model != runner.CUSTOM_MODEL_CHOICE
        assert states[0].model == runner.DEFAULT_EVAL_MODEL

    def test_a_filled_custom_id_still_overrides_the_select(self):
        _register_case("database/case-1")

        states = runner._submit_from_form(
            {
                "case_ids": ["database/case-1"],
                "model": [runner.CUSTOM_MODEL_CHOICE],
                "model_custom": ["openai:gpt-5.6-luna"],
            }
        )

        assert states[0].model == "openai:gpt-5.6-luna"


class TestNotes:
    def test_notes_reach_the_executor_and_the_runs_payload(self):
        _register_case("database/case-1")
        stub = MagicMock(return_value={"experiment_id": "exp-1"})
        runner.start_worker(executor=stub)

        runner._submit_from_form(
            {"case_ids": ["database/case-1"], "notes": ["reasoning_effort=none"]}
        )
        runner._run_queue.join()

        assert stub.call_args.kwargs["notes"] == "reasoning_effort=none"
        payload = json.loads(runner._runs_json())
        assert payload["runs"][0]["notes"] == "reasoning_effort=none"

    def test_blank_notes_are_stored_as_none(self):
        _register_case("database/case-1")

        states = runner._submit_from_form(
            {"case_ids": ["database/case-1"], "notes": ["   "]}
        )

        assert states[0].notes is None


class TestProgressAndStop:
    def test_runs_json_exposes_the_live_counter(self):
        _register_case("database/case-1")
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        state.status = "running"
        state.control.set_total(38)
        state.control.case_finished()

        run = json.loads(runner._runs_json())["runs"][0]

        assert (run["completed"], run["total"]) == (1, 38)
        assert run["stopping"] is False

    def test_stop_marks_queued_and_running_runs_only(self):
        queued = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        running = runner.submit_run(dataset="kuma-core", model="m", runs=1)
        running.status = "running"
        finished = runner.submit_run(dataset="kuma-docs", model="m", runs=1)
        finished.status = "done"

        assert runner.stop_runs() == 2
        assert queued.control.stopping
        assert running.control.stopping
        assert not finished.control.stopping

    def test_stop_can_target_a_single_run(self):
        first = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        second = runner.submit_run(dataset="kuma-core", model="m", runs=1)

        assert runner.stop_runs(second.id) == 1
        assert not first.control.stopping
        assert second.control.stopping

    def test_a_run_stopped_while_queued_never_calls_the_executor(self):
        stub = MagicMock(return_value={"experiment_id": "exp-1"})
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        state.control.stop()

        runner.start_worker(executor=stub)
        runner._run_queue.join()

        stub.assert_not_called()
        assert state.status == "stopped"
        assert state.finished_at is not None

    def test_a_run_stopped_mid_flight_ends_as_stopped_not_done(self):
        def executor(**kwargs):
            kwargs["control"].stop()
            return {"experiment_id": "exp-1"}

        runner.start_worker(executor=executor)
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        runner._run_queue.join()

        assert state.status == "stopped"

    def test_stop_endpoint_reports_how_many_it_stopped(self):
        runner.submit_run(dataset="kuma-database", model="m", runs=1)
        app = runner.make_wsgi_app()

        status, _headers, body = _call_wsgi(app, "POST", "/stop", b"")

        assert status.startswith("200")
        assert json.loads(body)["stopped"] == 1

    def test_stop_endpoint_refuses_a_non_local_request(self):
        app = runner.make_wsgi_app()

        status, _headers, _body = _call_wsgi(
            app, "POST", "/stop", b"", extra_environ={"HTTP_HOST": "evil.example.com"}
        )

        assert status.startswith("403")


class TestRunLogCapture:
    def test_the_sink_attributes_lines_to_the_active_run(self, monkeypatch):
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        monkeypatch.setattr(runner, "_active_run", state)

        runner._log_sink("13:05:41 INFO    run docs/webhooks-intro\n")

        assert runner.run_log(state.id) == ["13:05:41 INFO    run docs/webhooks-intro"]

    def test_lines_logged_with_no_active_run_are_dropped(self, monkeypatch):
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        monkeypatch.setattr(runner, "_active_run", None)

        runner._log_sink("noise from the request thread\n")

        assert runner.run_log(state.id) == []

    def test_the_buffer_keeps_only_the_most_recent_lines(self, monkeypatch):
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        monkeypatch.setattr(runner, "_active_run", state)

        for index in range(runner.LOG_LINES + 10):
            runner._log_sink(f"line {index}\n")

        lines = runner.run_log(state.id)
        assert len(lines) == runner.LOG_LINES
        assert lines[0] == "line 10"
        assert lines[-1] == f"line {runner.LOG_LINES + 9}"

    def test_run_log_endpoint_returns_lines_for_a_known_run(self, monkeypatch):
        state = runner.submit_run(dataset="kuma-database", model="m", runs=1)
        monkeypatch.setattr(runner, "_active_run", state)
        runner._log_sink("hello\n")
        app = runner.make_wsgi_app()

        status, _headers, body = _call_wsgi(
            app,
            "GET",
            "/run-log.json",
            extra_environ={"QUERY_STRING": f"id={state.id}"},
        )

        assert status.startswith("200")
        assert json.loads(body)["lines"] == ["hello"]

    def test_run_log_endpoint_404s_for_an_unknown_run(self):
        app = runner.make_wsgi_app()

        status, _headers, _body = _call_wsgi(
            app, "GET", "/run-log.json", extra_environ={"QUERY_STRING": "id=nope"}
        )

        assert status.startswith("404")
