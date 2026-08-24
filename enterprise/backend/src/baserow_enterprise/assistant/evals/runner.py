"""Minimal wsgiref app + single worker thread powering the eval runner page.

``submit_run`` only enqueues; a single daemon worker thread (started once by
the ``assistant_eval_runner`` management command via ``start_worker``) drains
the queue and executes each run through ``run.run_experiment_for``. Run state
lives in-memory only — history is not meant to survive a restart, Phoenix is
the durable record.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qs

from django.conf import settings
from django.template.loader import render_to_string

from loguru import logger

from baserow_enterprise.assistant.evals.models import (
    DEFAULT_EVAL_MODEL,
    available_models,
)
from baserow_enterprise.assistant.evals.registry import cases_by_dataset
from baserow_enterprise.assistant.evals.run import run_experiment_for

MAX_HISTORY = 50
MAX_FORM_BYTES = 64 * 1024

RunStatus = Literal["queued", "running", "done", "failed"]


@dataclass
class RunnerState:
    id: str
    dataset: str
    case_ids: list[str] | None
    model: str
    runs: int
    experiment_name: str | None = None
    status: RunStatus = "queued"
    error: str | None = None
    experiment_info: Any = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None


_history: deque[RunnerState] = deque(maxlen=MAX_HISTORY)
_history_lock = threading.Lock()
_run_queue: queue.Queue[RunnerState] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def recent_runs() -> list[RunnerState]:
    """Most recent run first."""

    with _history_lock:
        return list(reversed(_history))


def submit_run(
    dataset: str,
    model: str,
    case_ids: list[str] | None = None,
    runs: int = 1,
    experiment_name: str | None = None,
) -> RunnerState:
    state = RunnerState(
        id=uuid.uuid4().hex,
        dataset=dataset,
        case_ids=case_ids or None,
        model=model,
        runs=runs,
        experiment_name=experiment_name,
    )
    with _history_lock:
        _history.append(state)
    _run_queue.put(state)
    return state


def _run_one(state: RunnerState, executor: Callable[..., Any]) -> None:
    state.status = "running"
    state.started_at = datetime.now(timezone.utc)
    try:
        state.experiment_info = executor(
            dataset_name=state.dataset,
            model=state.model,
            case_ids=state.case_ids,
            runs=state.runs,
            experiment_name=state.experiment_name,
        )
        state.status = "done"
    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        logger.exception(f"Eval run {state.id} ({state.dataset}) failed")
    finally:
        state.finished_at = datetime.now(timezone.utc)


def _worker_loop(executor: Callable[..., Any]) -> None:
    while True:
        state = _run_queue.get()
        try:
            _run_one(state, executor)
        finally:
            _run_queue.task_done()


def start_worker(executor: Callable[..., Any] | None = None) -> None:
    """Start the single background worker thread. Idempotent."""

    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        target = executor or run_experiment_for
        threading.Thread(target=_worker_loop, args=(target,), daemon=True).start()
        _worker_started = True


class _FormTooLarge(Exception):
    pass


class _FormNotUtf8(Exception):
    pass


def _parse_form(environ: dict) -> dict[str, list[str]]:
    """Read and decode the request body, bounded so a lying Content-Length
    can't block the single-threaded wsgiref server (including /healthz)."""

    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length <= 0:
        return {}
    if length > MAX_FORM_BYTES:
        raise _FormTooLarge()
    body = environ["wsgi.input"].read(length)
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError:
        raise _FormNotUtf8() from None
    return parse_qs(decoded)


def _first(form: dict[str, list[str]], key: str, default: str = "") -> str:
    values = form.get(key)
    return values[0] if values else default


def _submit_from_form(form: dict[str, list[str]]) -> RunnerState:
    dataset = _first(form, "dataset")
    model = _first(form, "model_custom").strip() or _first(
        form, "model", DEFAULT_EVAL_MODEL
    )
    case_ids = form.get("case_ids") or None
    try:
        runs = max(1, int(_first(form, "runs", "1")))
    except ValueError:
        runs = 1
    experiment_name = _first(form, "experiment_name").strip() or None
    return submit_run(
        dataset=dataset,
        model=model,
        case_ids=case_ids,
        runs=runs,
        experiment_name=experiment_name,
    )


def _render_index() -> str:
    grouped = cases_by_dataset()
    context = {
        "datasets": [{"name": name, "cases": cases} for name, cases in grouped.items()],
        "models": available_models(),
        "default_model": DEFAULT_EVAL_MODEL,
        "phoenix_url": getattr(settings, "BASEROW_ASSISTANT_PHOENIX_URL", ""),
        "runs": recent_runs(),
    }
    return render_to_string("baserow_enterprise/eval_runner.html", context)


def make_wsgi_app() -> Callable[[dict, Callable], Iterable[bytes]]:
    """Build the stdlib WSGI app served by the ``assistant_eval_runner`` command."""

    def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/healthz":
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        if method == "GET" and path == "/":
            body = _render_index().encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        if method == "POST" and path == "/run":
            try:
                form = _parse_form(environ)
            except _FormTooLarge:
                start_response(
                    "413 Payload Too Large", [("Content-Type", "text/plain")]
                )
                return [b"form body too large"]
            except _FormNotUtf8:
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"form body must be utf-8"]
            _submit_from_form(form)
            start_response("303 See Other", [("Location", "/")])
            return [b""]

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"not found"]

    return application
