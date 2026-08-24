from __future__ import annotations

import io
import queue as queue_module
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from django.core.management import call_command

import pytest

from baserow_enterprise.assistant.evals import registry, runner
from baserow_enterprise.assistant.evals.types import EvalCase


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "_cases", {})
    monkeypatch.setattr(registry, "_scenarios", {})


@pytest.fixture(autouse=True)
def _isolated_runner_state(monkeypatch):
    monkeypatch.setattr(runner, "_history", runner.deque(maxlen=runner.MAX_HISTORY))
    monkeypatch.setattr(runner, "_run_queue", queue_module.Queue())
    monkeypatch.setattr(runner, "_worker_started", False)


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
):
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
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


class TestHealthz:
    def test_healthz_returns_200(self):
        app = runner.make_wsgi_app()

        status, _headers, _body = _call_wsgi(app, "GET", "/healthz")

        assert status == "200 OK"


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


@pytest.mark.django_db
class TestAssistantEvalRunnerCommand:
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
        mock_start_worker.assert_called_once()
        mock_make_server.assert_called_once()
        assert mock_make_server.call_args[0][0] == "0.0.0.0"  # noqa: S104
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
