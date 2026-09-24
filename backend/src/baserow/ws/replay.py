"""Isolate optional replay reads from the shared WebSocket database executor."""

import asyncio
import os
import threading
from collections import deque
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import partial
from time import monotonic

from django.db import DatabaseError, connection, connections, transaction

from opentelemetry import metrics
from opentelemetry.metrics import Observation

from baserow.ws.realtime_events import (
    FIRST_CONNECT_CURSOR,
    NO_REPLAY_AVAILABLE,
    RealtimeEventHandler,
    ReplayEventsResult,
)
from baserow.ws.telemetry import run_database_sync

# Internal resource budgets per ASGI worker. Waiting replay requests consume no
# thread or database connection, and their wait counts toward the same deadline.
REPLAY_MAX_CONCURRENCY = 2
REPLAY_MAX_PENDING = 8
REPLAY_TIMEOUT_SECONDS = 3
REPLAY_RETRY_AFTER_MS = 1000

meter = metrics.get_meter(__name__)
websocket_replay_requests = meter.create_counter(
    "baserow.websocket_replay_requests",
    unit="1",
    description="Replay decisions, including overload and deadline fallbacks.",
)
websocket_replay_duration = meter.create_histogram(
    "baserow.websocket_replay_duration",
    unit="ms",
    description="Total time a WebSocket waits for a replay decision.",
)
websocket_replay_database_errors = meter.create_counter(
    "baserow.websocket_replay_database_errors",
    unit="1",
    description="Replay database failures, including work finishing after a deadline.",
)
websocket_replay_events = meter.create_histogram(
    "baserow.websocket_replay_events",
    unit="1",
    description="Events returned in each completed replay decision.",
)
websocket_replay_inflight = meter.create_up_down_counter(
    "baserow.websocket_replay_inflight",
    unit="1",
    description="Replay pool slots reserved, including timed-out work still running.",
)
websocket_replay_queued = meter.create_up_down_counter(
    "baserow.websocket_replay_queued",
    unit="1",
    description="Replay requests waiting for admission to the dedicated pool.",
)
websocket_replay_queue_duration = meter.create_histogram(
    "baserow.websocket_replay_queue_duration",
    unit="ms",
    description="Time awaiting replay pool admission, including cancelled waits.",
)


class ReplayOverloaded(Exception):
    pass


class _ReplayReservation(Executor):
    """One admitted submission; capacity follows the real concurrent future."""

    def __init__(self, pool):
        self.pool = pool
        self.submitted = False
        self.released = False
        self._lock = threading.Lock()

    def release(self, future=None):
        with self._lock:
            if self.released:
                return
            self.released = True
        self.pool._release()

    def submit(self, fn, /, *args, **kwargs):
        if self.submitted or self.released:
            raise RuntimeError("Replay reservation has already been used")
        self.submitted = True
        try:
            future = self.pool._threads.submit(fn, *args, **kwargs)
        except BaseException:
            self.release()
            raise
        future.add_done_callback(self.release)
        return future


class ReplayExecutor:
    """A bounded FIFO admission queue in front of a dedicated thread pool.

    Only admitted work reaches ThreadPoolExecutor. In particular, cancelling
    queued requests removes them immediately instead of accumulating cancelled
    work items in ThreadPoolExecutor's unbounded internal queue.
    """

    def __init__(self, max_workers, max_pending=REPLAY_MAX_PENDING):
        self.max_concurrency = max_workers
        self.max_pending = max_pending
        self._threads = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="websocket-replay"
        )
        self._lock = threading.Lock()
        self._active = 0
        self._waiters = deque()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()

    def shutdown(self, wait=True):
        self._threads.shutdown(wait=wait)

    async def acquire(self):
        started_at = monotonic()
        try:
            with self._lock:
                if self._active < self.max_concurrency:
                    self._active += 1
                    websocket_replay_inflight.add(1, {"process.pid": os.getpid()})
                    return _ReplayReservation(self)
                if len(self._waiters) >= self.max_pending:
                    raise ReplayOverloaded
                waiter = asyncio.get_running_loop().create_future()
                self._waiters.append(waiter)
                websocket_replay_queued.add(1, {"process.pid": os.getpid()})
            try:
                return await waiter
            except BaseException:
                with self._lock:
                    if waiter in self._waiters:
                        self._waiters.remove(waiter)
                        websocket_replay_queued.add(-1, {"process.pid": os.getpid()})
                # A completed handoff can race with cancellation of the awaiter.
                # Pending handoffs detect cancelled Futures in _deliver instead.
                if waiter.done() and not waiter.cancelled():
                    waiter.result().release()
                raise
        finally:
            websocket_replay_queue_duration.record(
                (monotonic() - started_at) * 1000, {"process.pid": os.getpid()}
            )

    def _deliver(self, waiter):
        reservation = _ReplayReservation(self)
        if waiter.cancelled():
            reservation.release()
        else:
            waiter.set_result(reservation)

    def _release(self):
        while True:
            waiter = None
            with self._lock:
                self._active -= 1
                websocket_replay_inflight.add(-1, {"process.pid": os.getpid()})
                if self._waiters:
                    waiter = self._waiters.popleft()
                    websocket_replay_queued.add(-1, {"process.pid": os.getpid()})
                    # Reserve before scheduling the wakeup to preserve FIFO ordering.
                    self._active += 1
                    websocket_replay_inflight.add(1, {"process.pid": os.getpid()})
            if waiter is None:
                return
            try:
                waiter.get_loop().call_soon_threadsafe(self._deliver, waiter)
            except RuntimeError:
                # Release this handoff's reserved slot if its loop has closed,
                # then try the next waiter.
                continue
            return


_executor = None
_executor_lock = threading.Lock()
_pending_replays = set()


def _observe_capacity(options):
    # Importing this module does not establish that the process serves replay.
    # Export only an initialized pool, rather than counting configured capacity
    # in unrelated processes or resolving Django settings from the exporter.
    executor = _executor
    if executor is None:
        return []
    return [Observation(executor.max_concurrency, {"process.pid": os.getpid()})]


meter.create_observable_gauge(
    "baserow.websocket_replay_capacity",
    callbacks=[_observe_capacity],
    unit="1",
    description="Maximum concurrent jobs in this process's initialized replay pool.",
)


def _observe_queue_capacity(options):
    executor = _executor
    if executor is None:
        return []
    return [Observation(executor.max_pending, {"process.pid": os.getpid()})]


meter.create_observable_gauge(
    "baserow.websocket_replay_queue_capacity",
    callbacks=[_observe_queue_capacity],
    unit="1",
    description="Maximum waiting requests in this process's initialized replay pool.",
)


def _get_executor():
    global _executor

    with _executor_lock:
        if _executor is None:
            _executor = ReplayExecutor(REPLAY_MAX_CONCURRENCY)
        return _executor


def _force_refresh():
    return ReplayEventsResult(
        True, NO_REPLAY_AVAILABLE, [], refresh_reason="missing_cursor"
    )


def _retry_later():
    # Older clients still understand the conservative force-refresh fallback.
    return ReplayEventsResult(
        True, NO_REPLAY_AVAILABLE, [], retry_after_ms=REPLAY_RETRY_AFTER_MS
    )


def _database_error_reason(exc):
    cause = exc.__cause__
    sqlstate = getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
    return "query_timeout" if sqlstate == "57014" else "database_error"


def _remaining_timeout_ms(deadline):
    remaining = int((deadline - monotonic()) * 1000)
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _read_replay_events(
    user_id, page_group_names, last_seen_id, web_socket_id, deadline
):
    try:
        _remaining_timeout_ms(deadline)
        # RealtimeEvent is UNLOGGED and its router always uses the primary DB.
        # LOCAL settings disappear on commit/rollback and preserve a stricter
        # pre-existing statement timeout. Never change the session timeout.
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Queueing, adapter cleanup and establishing the connection all
                # consume the response budget; do not restart it at query entry.
                timeout = f"{_remaining_timeout_ms(deadline)}ms"
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true) "
                    "WHERE current_setting('statement_timeout')::interval = "
                    "interval '0' OR current_setting('statement_timeout')::interval "
                    "> %s::interval",
                    [timeout, timeout],
                )
            return RealtimeEventHandler.get_replay_events_result(
                user_id, page_group_names, last_seen_id, web_socket_id
            )
    except DatabaseError as exc:
        websocket_replay_database_errors.add(
            1, {"process.pid": os.getpid(), "reason": _database_error_reason(exc)}
        )
        raise
    finally:
        # A dedicated pool adds a bounded number of connections under load, but
        # must not retain them when idle (even with CONN_MAX_AGE=None).
        connections["default"].close()


def _replay_finished(task, reservation):
    _pending_replays.discard(task)
    # Also covers cancellation before the coroutine's first step: its own
    # finally block would not run, and no concurrent future owns the slot yet.
    if not reservation.submitted:
        reservation.release()
    if not task.cancelled():
        # Retrieve errors from work that outlives its caller's deadline/cancel.
        task.exception()


async def get_replay_events_result(
    user_id, page_group_names, last_seen_id, web_socket_id
) -> ReplayEventsResult:
    """Replay within bounded capacity/time, retrying temporary resource failures.

    The deadline also bounds connection establishment and Python-side work, which
    PostgreSQL's statement timeout cannot cover. A timed-out thread retains its
    capacity until it finishes. Waiting requests are bounded and can be cancelled
    without submitting work to the thread pool.
    """

    started_at = monotonic()
    outcome = "error"
    reason = "none"
    try:
        if last_seen_id == NO_REPLAY_AVAILABLE:
            result = _force_refresh()
        else:
            deadline = started_at + REPLAY_TIMEOUT_SECONDS
            async with asyncio.timeout(max(0, deadline - monotonic())):
                reservation = await _get_executor().acquire()
                task = asyncio.create_task(
                    run_database_sync(
                        "replay",
                        _read_replay_events,
                        user_id,
                        page_group_names,
                        last_seen_id,
                        web_socket_id,
                        deadline,
                        executor=reservation,
                    )
                )
                _pending_replays.add(task)
                task.add_done_callback(
                    partial(_replay_finished, reservation=reservation)
                )
                result = await asyncio.shield(task)
        if result.force_refresh:
            outcome = "refresh"
            reason = result.refresh_reason or "unknown"
        elif last_seen_id == FIRST_CONNECT_CURSOR:
            outcome = "baseline"
        else:
            outcome = "replayed"
        websocket_replay_events.record(
            len(result.replay_events), {"process.pid": os.getpid(), "outcome": outcome}
        )
        return result
    except ReplayOverloaded:
        outcome = "overloaded"
        return _retry_later()
    except TimeoutError:
        outcome = "deadline_exceeded"
        return _retry_later()
    except DatabaseError as exc:
        outcome = _database_error_reason(exc)
        return _retry_later()
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    finally:
        attributes = {"process.pid": os.getpid(), "outcome": outcome, "reason": reason}
        websocket_replay_requests.add(1, attributes)
        websocket_replay_duration.record((monotonic() - started_at) * 1000, attributes)
