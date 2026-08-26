"""Minimal wsgiref app + single worker thread powering the eval runner page.

``submit_run`` only enqueues; a single daemon worker thread (started once by
the ``assistant_eval_runner`` management command via ``start_worker``) drains
the queue and executes each run through ``run.run_experiment_for``. Run state
lives in-memory only — history is not meant to survive a restart, Phoenix is
the durable record.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import uuid
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.template.loader import render_to_string

import httpx
from loguru import logger

from baserow_enterprise.assistant.evals.baseline import _api_base, _headers
from baserow_enterprise.assistant.evals.control import RunControl
from baserow_enterprise.assistant.evals.gitinfo import get_git_info
from baserow_enterprise.assistant.evals.models import (
    DEFAULT_EVAL_MODEL,
    available_models,
)
from baserow_enterprise.assistant.evals.prompt_sync import SYNCED_PROMPTS
from baserow_enterprise.assistant.evals.registry import (
    cases_by_dataset,
    get_case,
    load_all,
)
from baserow_enterprise.assistant.evals.run import (
    UI_CASE_PREFIX,
    prompt_from_example_input,
    run_experiment_for,
)

MAX_HISTORY = 50
MAX_FORM_BYTES = 64 * 1024

HELP_DOCS = (
    ("evals", "Running evals", "docs/testing/ai-assistant-evals.md"),
    ("analysis", "Evaluating results", "docs/testing/ai-assistant-eval-analysis.md"),
    ("tracing", "Phoenix & tracing", "docs/development/ai-assistant-tracing.md"),
)

# The select's "Custom…" option; the free-text field carries the real id.
CUSTOM_MODEL_CHOICE = "__custom"

RunStatus = Literal["queued", "running", "done", "failed", "stopped"]

LOG_LINES = 200


@dataclass
class RunnerState:
    id: str
    dataset: str
    case_ids: list[str] | None
    model: str
    runs: int
    experiment_name: str | None = None
    prompt_overrides: list[str] | None = None
    notes: str | None = None
    status: RunStatus = "queued"
    error: str | None = None
    experiment_info: Any = None
    phoenix_link: str | None = None
    git_label: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Live-only: a restart rewrites in-flight runs to failed, so neither survives.
    control: RunControl = field(default_factory=RunControl)
    log: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_LINES))


_history: deque[RunnerState] = deque(maxlen=MAX_HISTORY)
_history_lock = threading.Lock()
_run_queue: queue.Queue[RunnerState] = queue.Queue()
_active_run: RunnerState | None = None
_log_lock = threading.Lock()
_worker_started = False
_worker_lock = threading.Lock()

# Survives watch-py process restarts (every .py edit); dies with the container.
_HISTORY_FILE = os.environ.get(
    "BASEROW_EVAL_RUNNER_HISTORY_FILE",
    "/tmp/baserow-eval-runner-history.json",  # noqa: S108 single-user container
)
_PERSISTED_FIELDS = (
    "id",
    "dataset",
    "case_ids",
    "model",
    "runs",
    "experiment_name",
    "prompt_overrides",
    "notes",
    "status",
    "error",
    "phoenix_link",
    "git_label",
)
_TS_FIELDS = ("created_at", "started_at", "finished_at")


def recent_runs() -> list[RunnerState]:
    """Most recent run first."""

    with _history_lock:
        return list(reversed(_history))


def _save_history() -> None:
    try:
        with _history_lock:
            payload = [
                {
                    **{name: getattr(state, name) for name in _PERSISTED_FIELDS},
                    **{
                        name: value.isoformat()
                        if (value := getattr(state, name))
                        else None
                        for name in _TS_FIELDS
                    },
                }
                for state in _history
            ]
        with open(_HISTORY_FILE, "w") as handle:
            json.dump(payload, handle)
    except OSError as exc:
        logger.warning("Could not persist eval runner history: {}", exc)


def load_history() -> None:
    """Restore past runs on startup; mid-flight ones are marked interrupted."""

    try:
        with open(_HISTORY_FILE) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return
    with _history_lock:
        _history.clear()
        for entry in payload:
            state = RunnerState(
                **{name: entry.get(name) for name in _PERSISTED_FIELDS},
                **{
                    name: datetime.fromisoformat(value)
                    if (value := entry.get(name))
                    else None
                    for name in _TS_FIELDS
                },
            )
            if state.status in ("queued", "running"):
                state.status = "failed"
                state.error = "interrupted by runner restart"
            _history.append(state)


def _git_label() -> str | None:
    """Compact "branch@commit" for the runs table, or just whichever resolved."""

    info = get_git_info()
    branch, commit = info.get("git_branch"), info.get("git_commit")
    if branch and commit:
        return f"{branch}@{commit}"
    return branch or commit or None


def submit_run(
    dataset: str,
    model: str,
    case_ids: list[str] | None = None,
    runs: int = 1,
    experiment_name: str | None = None,
    prompt_overrides: list[str] | None = None,
    notes: str | None = None,
) -> RunnerState:
    state = RunnerState(
        id=uuid.uuid4().hex,
        dataset=dataset,
        case_ids=case_ids or None,
        model=model,
        runs=runs,
        experiment_name=experiment_name,
        prompt_overrides=prompt_overrides or None,
        notes=notes or None,
        git_label=_git_label(),
    )
    with _history_lock:
        _history.append(state)
    _save_history()
    _run_queue.put(state)
    return state


def _run_one(state: RunnerState, executor: Callable[..., Any]) -> None:
    global _active_run

    if state.control.stopping:
        state.status = "stopped"
        state.finished_at = datetime.now(timezone.utc)
        _save_history()
        return

    state.status = "running"
    state.started_at = datetime.now(timezone.utc)
    _active_run = state
    _save_history()
    try:
        state.experiment_info = executor(
            dataset_name=state.dataset,
            model=state.model,
            case_ids=state.case_ids,
            runs=state.runs,
            experiment_name=state.experiment_name,
            prompt_overrides=state.prompt_overrides,
            notes=state.notes,
            control=state.control,
        )
        state.status = "stopped" if state.control.stopping else "done"
    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        logger.exception(f"Eval run {state.id} ({state.dataset}) failed")
    finally:
        _active_run = None
        state.finished_at = datetime.now(timezone.utc)
        if state.status in ("done", "stopped"):
            state.phoenix_link = _phoenix_link(
                state.experiment_info, _phoenix_public_url()
            )
        _save_history()


def _log_sink(message: Any) -> None:
    state = _active_run
    if state is None:
        return
    with _log_lock:
        state.log.append(str(message).rstrip())


def run_log(run_id: str) -> list[str] | None:
    """Snapshot of a run's captured log, or None when the run is unknown."""

    for state in recent_runs():
        if state.id == run_id:
            with _log_lock:
                return list(state.log)
    return None


def stop_runs(run_id: str | None = None) -> int:
    """Stop one run, or every queued and in-flight run. Returns how many."""

    stopped = 0
    for state in recent_runs():
        if run_id is not None and state.id != run_id:
            continue
        if state.status in ("queued", "running"):
            state.control.stop()
            stopped += 1
    return stopped


def _worker_loop(executor: Callable[..., Any]) -> None:
    # Installed here so the filter can pin the worker thread: the WSGI thread
    # logs too, and its lines must not be attributed to the running eval.
    worker_thread_id = threading.get_ident()
    logger.add(
        _log_sink,
        level=os.environ.get("BASEROW_EVAL_RUNNER_LOG_LEVEL") or "INFO",
        filter=lambda record: record["thread"].id == worker_thread_id,
        format="{time:HH:mm:ss} {level: <7} {message}",
    )
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


_ALLOWED_HOSTNAMES = {"localhost", "127.0.0.1"}


def _is_allowed_hostname(hostname: str | None) -> bool:
    return hostname in _ALLOWED_HOSTNAMES


def _request_is_local(environ: dict) -> bool:
    """CSRF guard: reject POSTs whose Host/Origin aren't loopback names.

    Headers are client-supplied, so this stops cross-site browser requests
    only; network exposure is limited by the loopback port publish and the
    server's 127.0.0.1 default bind, not by this check.
    """

    if not _is_allowed_hostname(urlsplit(f"//{environ.get('HTTP_HOST', '')}").hostname):
        return False
    origin = environ.get("HTTP_ORIGIN")
    return not origin or _is_allowed_hostname(urlsplit(origin).hostname)


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


def _group_case_ids_by_dataset(case_ids: list[str]) -> dict[str, list[str]]:
    load_all()
    grouped: dict[str, list[str]] = {}
    for case_id in case_ids:
        if case_id.startswith(UI_CASE_PREFIX):
            dataset = case_id.split(":", 2)[1]
        else:
            try:
                dataset = get_case(case_id).dataset
            except KeyError:
                continue
        grouped.setdefault(dataset, []).append(case_id)
    return grouped


def _new_experiment_name() -> str:
    """One name across the fan-out: the Results tab groups experiments by name."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{uuid.uuid4().hex[:4]}"


def _submit_from_form(form: dict[str, list[str]]) -> list[RunnerState]:
    """One queued run per dataset: selections spanning datasets fan out."""

    model = _first(form, "model_custom").strip() or _first(
        form, "model", DEFAULT_EVAL_MODEL
    )
    if model == CUSTOM_MODEL_CHOICE:
        model = DEFAULT_EVAL_MODEL
    try:
        runs = max(1, int(_first(form, "runs", "1")))
    except ValueError:
        runs = 1
    experiment_name = _first(form, "experiment_name").strip() or _new_experiment_name()

    notes = _first(form, "notes").strip() or None

    prompt_overrides = [
        name for name in form.get("prompt_overrides", []) if name in SYNCED_PROMPTS
    ]

    case_ids = form.get("case_ids") or []
    if case_ids:
        submissions = [
            (dataset, ids)
            for dataset, ids in sorted(_group_case_ids_by_dataset(case_ids).items())
        ]
    else:
        submissions = [(_first(form, "dataset"), None)]

    return [
        submit_run(
            dataset=dataset,
            model=model,
            case_ids=ids,
            runs=runs,
            experiment_name=experiment_name,
            prompt_overrides=prompt_overrides,
            notes=notes,
        )
        for dataset, ids in submissions
    ]


def _phoenix_public_url() -> str:
    """The browser-reachable Phoenix URL, distinct from the (container-internal)
    client URL used to talk to Phoenix from inside the compose network."""

    return os.environ.get("BASEROW_ASSISTANT_PHOENIX_PUBLIC_URL") or getattr(
        settings, "BASEROW_ASSISTANT_PHOENIX_URL", ""
    )


def _phoenix_link(experiment_info: Any, phoenix_public_url: str) -> str | None:
    """Deep-link a finished run's experiment when its ids are known, else the
    datasets list; ``None`` when no public Phoenix URL is configured."""

    if not phoenix_public_url:
        return None
    dataset_id = experiment_id = None
    if hasattr(experiment_info, "get"):
        dataset_id = experiment_info.get("dataset_id")
        experiment_id = experiment_info.get("experiment_id") or experiment_info.get(
            "id"
        )
    if dataset_id and experiment_id:
        return f"{phoenix_public_url}/datasets/{dataset_id}/compare?experimentId={experiment_id}"
    return f"{phoenix_public_url}/datasets"


_dataset_links: dict[str, str] = {}
_dataset_ids: dict[str, str] = {}
_ui_cases: dict[str, list[dict[str, str]]] = {}
_phoenix_client: Any = None

MAX_UI_CASE_LABEL = 60


def _ui_case_label(example: dict[str, Any]) -> str:
    prompt = prompt_from_example_input(example.get("input", {})) or "(no prompt)"
    if len(prompt) > MAX_UI_CASE_LABEL:
        return prompt[: MAX_UI_CASE_LABEL - 1] + "…"
    return prompt


def refresh_dataset_state(client: Any) -> None:
    """Resolve Phoenix deep links and UI-added examples per dataset, best-effort.

    Remembers the client so every page render can refresh — a UI-added example
    shows up on the next reload without a runner restart.
    """

    global _phoenix_client
    _phoenix_client = client
    public_url = _phoenix_public_url()
    for name in cases_by_dataset():
        try:
            dataset = client.datasets.get_dataset(dataset=name)
        except Exception as exc:
            logger.warning("Could not fetch Phoenix dataset {}: {}", name, exc)
            continue
        _dataset_ids[name] = dataset.id
        if public_url:
            _dataset_links[name] = f"{public_url}/datasets/{dataset.id}/examples"
        _ui_cases[name] = [
            {"value": f"{UI_CASE_PREFIX}{name}:{ex['id']}", "label": _ui_case_label(ex)}
            for ex in dataset.examples
            if not ex.get("metadata", {}).get("case_id")
        ]


_EXPERIMENT_SUMMARIES_QUERY = """
query ($datasetId: ID!) {
  node(id: $datasetId) {
    ... on Dataset {
      experiments(first: 50) {
        edges {
          node {
            id
            name
            createdAt
            metadata
            runCount
            averageRunLatencyMs
            costSummary { total { cost tokens } }
            annotationSummaries { annotationName meanScore }
          }
        }
      }
    }
  }
}
"""


# Only the settings that plausibly move a score; the rest is noise in a table.
_REPORTED_SETTINGS = ("temperature", "openai_reasoning_effort", "max_tokens")


def _settings_label(metadata: dict[str, Any]) -> str | None:
    """Compact "temperature=0.3 reasoning=none" for the results table."""

    settings = metadata.get("model_settings") or {}
    parts = [
        f"{key.replace('openai_reasoning_effort', 'reasoning')}={settings[key]}"
        for key in _REPORTED_SETTINGS
        if key in settings
    ]
    return " ".join(parts) or None


def _experiment_summaries(dataset_node_id: str) -> list[dict[str, Any]]:
    """Per-experiment mean scores for a dataset, newest first, via GraphQL."""

    response = httpx.post(
        f"{_api_base()}/graphql",
        json={
            "query": _EXPERIMENT_SUMMARIES_QUERY,
            "variables": {"datasetId": dataset_node_id},
        },
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    edges = response.json()["data"]["node"]["experiments"]["edges"]
    return [edge["node"] for edge in edges]


def _results_json() -> bytes:
    """Cross-dataset results: every experiment's mean scores, per dataset."""

    public_url = _phoenix_public_url()
    datasets = []
    for name, cases in cases_by_dataset().items():
        experiments: list[dict[str, Any]] = []
        node_id = _dataset_ids.get(name)
        if node_id:
            try:
                summaries = _experiment_summaries(node_id)
            except Exception as exc:
                logger.warning("Could not fetch results for {}: {}", name, exc)
                summaries = []
            for node in summaries:
                metadata = node.get("metadata") or {}
                git_label = "@".join(
                    part
                    for part in (
                        metadata.get("git_branch"),
                        metadata.get("git_commit"),
                    )
                    if part
                )
                # Imported baselines carry no traces, so live latency/cost
                # fall back to the totals frozen at capture time.
                totals = metadata.get("baseline_totals") or {}
                run_count = node.get("runCount") or totals.get("run_count")
                avg_latency_ms = node.get("averageRunLatencyMs") or totals.get(
                    "average_run_latency_ms"
                )
                cost_total = (node.get("costSummary") or {}).get("total") or {}
                cost = cost_total.get("cost")
                if cost is None:
                    cost = totals.get("total_cost")
                tokens = cost_total.get("tokens")
                if tokens is None:
                    tokens = totals.get("total_tokens")
                experiments.append(
                    {
                        "id": node["id"],
                        "name": node.get("name") or "",
                        "created_at": node.get("createdAt"),
                        "model": metadata.get("model"),
                        "git_label": git_label or None,
                        "notes": metadata.get("notes"),
                        "settings": _settings_label(metadata),
                        "scores": {
                            s["annotationName"]: s["meanScore"]
                            for s in node.get("annotationSummaries", [])
                            if s.get("meanScore") is not None
                        },
                        "time_s": (
                            avg_latency_ms * run_count / 1000
                            if avg_latency_ms and run_count
                            else None
                        ),
                        "cost": cost,
                        "tokens": tokens,
                        "link": (
                            f"{public_url}/datasets/{node_id}/compare"
                            f"?experimentId={node['id']}"
                            if public_url
                            else None
                        ),
                    }
                )
        datasets.append(
            {"name": name, "case_count": len(cases), "experiments": experiments}
        )
    return json.dumps({"datasets": datasets}).encode("utf-8")


def _render_index() -> str:
    grouped = cases_by_dataset()
    if _phoenix_client is not None:
        refresh_dataset_state(_phoenix_client)
    phoenix_public_url = _phoenix_public_url()
    runs = recent_runs()
    for state in runs:
        if state.status == "done":
            state.phoenix_link = _phoenix_link(
                state.experiment_info, phoenix_public_url
            )
    context = {
        "datasets": [
            {
                "name": name,
                "label": name.removeprefix("kuma-"),
                "link": _dataset_links.get(name),
                "cases": [
                    {"id": case.id, "label": case.id.split("/", 1)[-1]}
                    for case in cases
                ],
                "ui_cases": _ui_cases.get(name, []),
            }
            for name, cases in grouped.items()
        ],
        "models": available_models(),
        "default_model": DEFAULT_EVAL_MODEL,
        "prompts": sorted(SYNCED_PROMPTS),
        "phoenix_prompts_link": (
            f"{phoenix_public_url}/prompts" if phoenix_public_url else None
        ),
        "runs": runs,
    }
    return render_to_string("baserow_enterprise/eval_runner.html", context)


def _fmt_ts(value: datetime | None) -> str:
    return value.strftime("%b %d, %H:%M:%S") if value else ""


def _runs_json() -> bytes:
    payload = [
        {
            "id": run.id,
            "dataset": run.dataset,
            "experiment_name": run.experiment_name,
            "case_ids": run.case_ids,
            "model": run.model,
            "git_label": run.git_label,
            "prompt_overrides": run.prompt_overrides,
            "notes": run.notes,
            "runs": run.runs,
            "status": run.status,
            "completed": run.control.completed,
            "total": run.control.total,
            "stopping": run.control.stopping,
            "started_at": _fmt_ts(run.started_at),
            "finished_at": _fmt_ts(run.finished_at),
            "phoenix_link": run.phoenix_link,
            "error": run.error,
        }
        for run in recent_runs()
    ]
    return json.dumps({"runs": payload}).encode("utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _docs_json() -> bytes:
    """The Help tab's docs, read fresh per request so edits show immediately."""

    root = _repo_root()
    docs = []
    for slug, title, rel_path in HELP_DOCS:
        try:
            markdown = (root / rel_path).read_text(encoding="utf-8")
        except OSError:
            markdown = ""
        docs.append(
            {"slug": slug, "title": title, "path": rel_path, "markdown": markdown}
        )
    return json.dumps({"docs": docs}).encode("utf-8")


def make_wsgi_app() -> Callable[[dict, Callable], Iterable[bytes]]:
    """Build the stdlib WSGI app served by the ``assistant_eval_runner`` command."""

    def application(environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/healthz":
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        if method == "GET" and path == "/results.json":
            body = _results_json()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        if method == "GET" and path == "/docs.json":
            body = _docs_json()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        if method == "GET" and path == "/run-log.json":
            run_id = parse_qs(environ.get("QUERY_STRING", "")).get("id", [""])[0]
            lines = run_log(run_id)
            if lines is None:
                start_response("404 Not Found", [("Content-Type", "text/plain")])
                return [b"unknown run"]
            body = json.dumps({"lines": lines}).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        if method == "GET" and path == "/runs.json":
            body = _runs_json()
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

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
            if not _request_is_local(environ):
                start_response("403 Forbidden", [("Content-Type", "text/plain")])
                return [b"forbidden"]
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

        if method == "POST" and path == "/stop":
            if not _request_is_local(environ):
                start_response("403 Forbidden", [("Content-Type", "text/plain")])
                return [b"forbidden"]
            try:
                form = _parse_form(environ)
            except (_FormTooLarge, _FormNotUtf8):
                start_response("400 Bad Request", [("Content-Type", "text/plain")])
                return [b"bad form body"]
            stopped = stop_runs(_first(form, "id") or None)
            body = json.dumps({"stopped": stopped}).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"not found"]

    return application
