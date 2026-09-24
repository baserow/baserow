"""Bounded, worker-local diagnostics for the WebSocket serving path."""

import asyncio
import os
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import monotonic
from weakref import WeakKeyDictionary

from asgiref.sync import SyncToAsync
from channels.db import DatabaseSyncToAsync
from loguru import logger
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
websocket_sync_queue_duration = meter.create_histogram(
    "baserow.websocket_sync_queue_duration",
    unit="ms",
    description="Time before synchronous WebSocket work starts on its executor.",
)
websocket_sync_execution_duration = meter.create_histogram(
    "baserow.websocket_sync_execution_duration",
    unit="ms",
    description="Synchronous WebSocket execution, including database cleanup.",
)
websocket_sync_pending = meter.create_up_down_counter(
    "baserow.websocket_sync_pending",
    unit="1",
    description="WebSocket synchronous calls awaiting completion (queued or running).",
)
websocket_sync_executing = meter.create_up_down_counter(
    "baserow.websocket_sync_executing",
    unit="1",
    description="WebSocket synchronous calls currently executing on a thread.",
)
websocket_phase_duration = meter.create_histogram(
    "baserow.websocket_phase_duration",
    unit="ms",
    description="WebSocket authentication, handshake, and consumer phase duration.",
)
websocket_handshakes_pending = meter.create_up_down_counter(
    "baserow.websocket_handshakes_pending",
    unit="1",
    description="WebSocket applications waiting to accept or reject a handshake.",
)
websocket_event_loop_lag = meter.create_histogram(
    "baserow.websocket_event_loop_lag",
    unit="ms",
    description="Event loop scheduling delay while WebSocket applications are active.",
)
realtime_recording_events = meter.create_counter(
    "baserow.realtime_recording_events",
    unit="1",
    description="Envelopes in attempted recording batches, by destination and outcome.",
)
realtime_recording_batch_size = meter.create_histogram(
    "baserow.realtime_recording_batch_size",
    unit="1",
    description="Number of envelopes in each attempted recording batch.",
)
realtime_recording_duration = meter.create_histogram(
    "baserow.realtime_recording_duration",
    unit="ms",
    description="Recording handler duration, including serialization and database work.",
)
realtime_cleanup_deleted = meter.create_counter(
    "baserow.realtime_cleanup_deleted",
    unit="1",
    description="Realtime events removed by successfully committed cleanup batches.",
)
realtime_cleanup_batch_size = meter.create_histogram(
    "baserow.realtime_cleanup_batch_size",
    unit="1",
    description="Events removed by each successfully committed cleanup batch.",
)
realtime_cleanup_batch_duration = meter.create_histogram(
    "baserow.realtime_cleanup_batch_duration",
    unit="ms",
    description="Cleanup batch duration, including selection, deletion, and commit.",
)
realtime_cleanup_run_deleted = meter.create_histogram(
    "baserow.realtime_cleanup_run_deleted",
    unit="1",
    description="Events removed by committed batches within each cleanup run.",
)
realtime_cleanup_run_duration = meter.create_histogram(
    "baserow.realtime_cleanup_run_duration",
    unit="ms",
    description="Cleanup run duration, including successful batches before a failure.",
)
realtime_cleanup_skipped = meter.create_counter(
    "baserow.realtime_cleanup_skipped",
    unit="1",
    description="Scheduled cleanup attempts skipped before starting database work.",
)

_OPERATIONS = frozenset(
    {
        "authentication",
        "page_permission",
        "presence_space",
        "replay",
        "recording",
        "retention_cleanup",
    }
)
_PHASES = frozenset(
    {
        "authentication",
        "connect",
        "accept",
        "handshake",
        "replay_cursor",
        "replay_query",
    }
)
_connection_id = ContextVar("websocket_telemetry_connection_id", default="none")
_SLOW_OPERATION_SECONDS = 1.0
_SLOW_LOG_INTERVAL_SECONDS = 30.0
_EVENT_LOOP_INTERVAL_SECONDS = 1.0
_last_slow_log = {}
_slow_log_lock = threading.Lock()


def _attributes(**attributes):
    # A process label makes a single stalled worker visible instead of averaging it
    # into the healthy workers. Connection/user/table IDs are never metric labels.
    return {"process.pid": os.getpid(), **attributes}


@contextmanager
def realtime_recording(events_data):
    """Measure the actual recording call without traversing or serializing payloads.

    Counts describe attempted envelopes. A successful outcome means the handler
    returned, not that an enclosing application transaction has necessarily committed.
    Destination labels are bounded regardless of channel names or recipients.
    """

    started_at = monotonic()
    size = len(events_data)
    users = sum(channel_group == "users" for channel_group, _ in events_data)
    outcome = "success"
    try:
        yield
    except BaseException:
        outcome = "error"
        raise
    finally:
        attributes = _attributes(outcome=outcome)
        realtime_recording_duration.record(
            (monotonic() - started_at) * 1000, attributes
        )
        realtime_recording_batch_size.record(size, attributes)
        for destination, count in (("users", users), ("page", size - users)):
            if count:
                realtime_recording_events.add(
                    count, {**attributes, "destination": destination}
                )


@dataclass
class _CleanupStats:
    deleted: int = 0
    outcome: str = "success"


@contextmanager
def realtime_cleanup_batch():
    """Measure one batch; set ``deleted`` only after its transaction commits."""

    started_at = monotonic()
    stats = _CleanupStats()
    outcome = "success"
    try:
        yield stats
    except BaseException:
        outcome = "error"
        raise
    finally:
        attributes = _attributes(outcome=outcome)
        realtime_cleanup_batch_duration.record(
            (monotonic() - started_at) * 1000, attributes
        )
        if outcome == "success":
            realtime_cleanup_batch_size.record(stats.deleted, attributes)
            if stats.deleted:
                realtime_cleanup_deleted.add(stats.deleted, _attributes())


@contextmanager
def realtime_cleanup_run():
    """Measure cleanup progress, including committed work before an error or budget."""

    started_at = monotonic()
    stats = _CleanupStats()
    try:
        yield stats
    except BaseException:
        stats.outcome = "error"
        raise
    finally:
        outcome = (
            stats.outcome
            if stats.outcome in {"success", "budget", "error"}
            else "other"
        )
        attributes = _attributes(outcome=outcome)
        realtime_cleanup_run_duration.record(
            (monotonic() - started_at) * 1000, attributes
        )
        realtime_cleanup_run_deleted.record(stats.deleted, attributes)


def record_realtime_cleanup_skipped(reason):
    """Report an overlapping task or a failed lease acquisition without client data."""

    reason = reason if reason in {"overlap", "lock_error"} else "other"
    realtime_cleanup_skipped.add(1, _attributes(reason=reason))


def _log_slow(phase, operation, duration, connection_id):
    if duration < _SLOW_OPERATION_SECONDS:
        return
    now = monotonic()
    key = (phase, operation)
    with _slow_log_lock:
        if now - _last_slow_log.get(key, float("-inf")) < _SLOW_LOG_INTERVAL_SECONDS:
            return
        _last_slow_log[key] = now
    logger.warning(
        "Slow WebSocket operation: phase={} operation={} duration_ms={:.1f} "
        "pid={} connection_id={}",
        phase,
        operation,
        duration * 1000,
        os.getpid(),
        connection_id,
    )


def _record_phase(phase, started_at, outcome, connection_id):
    duration = monotonic() - started_at
    websocket_phase_duration.record(
        duration * 1000, _attributes(phase=phase, outcome=outcome)
    )
    _log_slow("phase", phase, duration, connection_id)
    logger.debug(
        "WebSocket phase complete: phase={} outcome={} duration_ms={:.1f} "
        "pid={} connection_id={}",
        phase,
        outcome,
        duration * 1000,
        os.getpid(),
        connection_id,
    )


@contextmanager
def websocket_phase(phase):
    """Time an async or sync phase without creating a connection-lifetime span."""

    phase = phase if phase in _PHASES else "other"
    started_at = monotonic()
    connection_id = _connection_id.get()
    outcome = "success"
    logger.debug(
        "WebSocket phase start: phase={} pid={} connection_id={}",
        phase,
        os.getpid(),
        connection_id,
    )
    try:
        yield
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        _record_phase(phase, started_at, outcome, connection_id)


class _SyncTimingMixin:
    def thread_handler(self, loop, *args, **kwargs):
        # This runs at the actual executor boundary, before DatabaseSyncToAsync's
        # connection cleanup. Timing the decorated function would mislabel cleanup
        # delays as queue wait and would miss cleanup after the function returns.
        started_at = monotonic()
        queue_duration = started_at - self.submitted_at
        websocket_sync_queue_duration.record(queue_duration * 1000, self.attributes)
        _log_slow("queue", self.operation, queue_duration, self.connection_id)
        websocket_sync_executing.add(1, self.attributes)
        outcome = "success"
        try:
            return super().thread_handler(loop, *args, **kwargs)
        except BaseException:
            outcome = "error"
            raise
        finally:
            duration = monotonic() - started_at
            websocket_sync_executing.add(-1, self.attributes)
            websocket_sync_execution_duration.record(
                duration * 1000, {**self.attributes, "outcome": outcome}
            )
            _log_slow("execution", self.operation, duration, self.connection_id)


class _TimedSyncToAsync(_SyncTimingMixin, SyncToAsync):
    pass


class _TimedDatabaseSyncToAsync(_SyncTimingMixin, DatabaseSyncToAsync):
    pass


async def _run_sync(adapter, operation, func, args, kwargs, executor):
    operation = operation if operation in _OPERATIONS else "other"
    call = adapter(func, thread_sensitive=executor is None, executor=executor)
    call.operation = operation
    call.connection_id = _connection_id.get()
    call.attributes = _attributes(
        operation=operation,
        executor="thread_sensitive" if executor is None else "isolated",
    )
    call.submitted_at = monotonic()
    websocket_sync_pending.add(1, call.attributes)
    try:
        return await call(*args, **kwargs)
    finally:
        # This measures awaiters. A cancelled caller can leave an already running
        # sync operation behind; websocket_sync_executing still measures that work.
        websocket_sync_pending.add(-1, call.attributes)


async def run_sync(operation, func, *args, executor=None, **kwargs):
    """Measure one real executor submission without adding synthetic queue probes."""

    return await _run_sync(_TimedSyncToAsync, operation, func, args, kwargs, executor)


async def run_database_sync(operation, func, *args, executor=None, **kwargs):
    """Like database_sync_to_async, with queue and full execution timing.

    Passing an executor explicitly opts out of the shared thread-sensitive executor.
    The caller must supply a bounded, reusable executor, never one per connection.
    """

    return await _run_sync(
        _TimedDatabaseSyncToAsync, operation, func, args, kwargs, executor
    )


class _EventLoopMonitor:
    """One timer per event loop, retained only while WebSocket scopes are active."""

    def __init__(self, loop):
        self.loop = loop
        self.connections = 0
        self.handle = None

    def acquire(self):
        self.connections += 1
        if self.handle is None:
            self._schedule()

    def release(self):
        self.connections -= 1
        if self.connections == 0 and self.handle is not None:
            self.handle.cancel()
            self.handle = None

    def _schedule(self):
        self.expected_at = self.loop.time() + _EVENT_LOOP_INTERVAL_SECONDS
        self.handle = self.loop.call_at(self.expected_at, self._tick)

    def _tick(self):
        delay = max(0, self.loop.time() - self.expected_at)
        websocket_event_loop_lag.record(delay * 1000, _attributes())
        _log_slow("event_loop", "lag", delay, "none")
        self._schedule()


_event_loop_monitors = WeakKeyDictionary()


class WebsocketTelemetryMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Deliberately independent of the client-provided web_socket_id, query
        # string and authentication token; no client values enter telemetry.
        connection_id = uuid.uuid4().hex
        token = _connection_id.set(connection_id)
        started_at = monotonic()
        attributes = _attributes()
        loop = asyncio.get_running_loop()
        monitor = _event_loop_monitors.get(loop)
        if monitor is None:
            monitor = _event_loop_monitors[loop] = _EventLoopMonitor(loop)
        monitor.acquire()
        websocket_handshakes_pending.add(1, attributes)
        pending = True
        outcome = "closed"
        logger.debug(
            "WebSocket handshake start: pid={} connection_id={}",
            os.getpid(),
            connection_id,
        )

        def finish_handshake(result):
            nonlocal pending
            if pending:
                pending = False
                websocket_handshakes_pending.add(-1, attributes)
                _record_phase("handshake", started_at, result, connection_id)

        async def measured_send(message):
            if message["type"] == "websocket.accept":
                with websocket_phase("accept"):
                    await send(message)
                finish_handshake("accepted")
            else:
                await send(message)
                if message["type"] == "websocket.close":
                    finish_handshake("rejected")

        try:
            return await self.inner(scope, receive, measured_send)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "error"
            raise
        finally:
            finish_handshake(outcome)
            monitor.release()
            if monitor.connections == 0:
                del _event_loop_monitors[loop]
            _connection_id.reset(token)
