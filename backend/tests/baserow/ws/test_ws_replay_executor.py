import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from time import monotonic
from unittest.mock import Mock, patch

from django.db import DatabaseError, OperationalError, connection

import pytest

from baserow.ws import replay
from baserow.ws.realtime_events import (
    FIRST_CONNECT_CURSOR,
    NO_REPLAY_AVAILABLE,
    ReplayEventsResult,
)


@pytest.fixture
def replay_executor(monkeypatch):
    executor = replay.ReplayExecutor(1, max_pending=2)
    monkeypatch.setattr(replay, "_executor", executor)
    yield executor
    executor.shutdown(wait=True)


async def finish_pending_replays():
    await asyncio.wait_for(
        asyncio.gather(*replay._pending_replays, return_exceptions=True), timeout=2
    )


@pytest.mark.asyncio
async def test_replay_taking_more_than_one_second_completes_with_default_budget(
    replay_executor,
):
    release = threading.Event()
    expected = ReplayEventsResult(False, 42, [])

    def read(*args):
        assert release.wait(5)
        return expected

    timer = asyncio.get_running_loop().call_later(1.1, release.set)
    try:
        with patch.object(replay, "_read_replay_events", side_effect=read):
            assert await replay.get_replay_events_result(1, [], 1, None) == expected
    finally:
        timer.cancel()
        release.set()
        await finish_pending_replays()


@pytest.mark.asyncio
async def test_replay_burst_waits_for_a_slot_instead_of_refreshing(replay_executor):
    entered, release = threading.Event(), threading.Event()
    expected = ReplayEventsResult(False, 42, [])

    def blocked_read(*args):
        entered.set()
        assert release.wait(5)
        return expected

    with patch.object(replay, "_read_replay_events", side_effect=blocked_read) as read:
        first = asyncio.create_task(replay.get_replay_events_result(1, [], 1, None))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            second = asyncio.create_task(
                replay.get_replay_events_result(2, [], 1, None)
            )
            done, _ = await asyncio.wait({second}, timeout=0.05)
            assert not done, "A short connection burst must wait for replay capacity"
            assert read.call_count == 1
        finally:
            release.set()
            assert await first == expected
            if second is not None:
                await second
            await finish_pending_replays()
        assert second.result() == expected


async def wait_for_queue_size(executor, size):
    async with asyncio.timeout(1):
        while len(executor._waiters) != size:
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_replay_queue_is_bounded_and_fifo(replay_executor):
    entered, release = threading.Event(), threading.Event()
    reads = []
    expected = ReplayEventsResult(False, 42, [])

    def blocked_read(user_id, *args):
        reads.append(user_id)
        entered.set()
        assert release.wait(5)
        return expected

    tasks = []
    with (
        patch.object(replay, "_read_replay_events", side_effect=blocked_read),
        patch.object(replay, "websocket_replay_requests") as requests,
    ):
        try:
            tasks.append(
                asyncio.create_task(replay.get_replay_events_result(1, [], 1, None))
            )
            assert await asyncio.to_thread(entered.wait, 2)
            for user_id in (2, 3):
                tasks.append(
                    asyncio.create_task(
                        replay.get_replay_events_result(user_id, [], 1, None)
                    )
                )
                await wait_for_queue_size(replay_executor, user_id - 1)
            result = await asyncio.wait_for(
                replay.get_replay_events_result(4, [], 1, None), timeout=0.25
            )
            assert result.retry_after_ms == 1000
            assert requests.add.call_args.args[1]["outcome"] == "overloaded"
            assert reads == [1]
        finally:
            release.set()
            assert await asyncio.gather(*tasks) == [expected] * len(tasks)
            await finish_pending_replays()
    assert reads == [1, 2, 3]
    assert replay_executor._active == 0
    assert not replay_executor._waiters


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "deadline"])
async def test_stopped_replay_keeps_capacity_until_thread_finishes(
    replay_executor, monkeypatch, stop
):
    entered, release = threading.Event(), threading.Event()
    expected = ReplayEventsResult(False, 42, [])
    replay_executor.max_pending = 0
    if stop == "deadline":
        monkeypatch.setattr(replay, "REPLAY_TIMEOUT_SECONDS", 0.05)

    def blocked_read(*args):
        entered.set()
        assert release.wait(5)
        return expected

    with (
        patch.object(replay, "_read_replay_events", side_effect=blocked_read) as read,
        patch.object(replay, "websocket_replay_requests") as requests,
    ):
        first = asyncio.create_task(replay.get_replay_events_result(1, [], 1, None))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            if stop == "cancel":
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
            else:
                assert (await asyncio.wait_for(first, timeout=1)).retry_after_ms == 1000
                assert requests.add.call_args.args[1]["outcome"] == "deadline_exceeded"

            # Active work continues to own its slot after the caller leaves.
            for _ in range(3):
                result = await replay.get_replay_events_result(1, [], 1, None)
                assert result.retry_after_ms == 1000
                assert requests.add.call_args.args[1]["outcome"] == "overloaded"
            assert read.call_count == 1
            assert replay_executor._active == 1
        finally:
            release.set()
            await finish_pending_replays()

        assert await replay.get_replay_events_result(1, [], 1, None) == expected
        assert read.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "deadline"])
async def test_stopped_waiters_are_removed_without_submitting_thread_work(
    replay_executor, monkeypatch, stop
):
    entered, release = threading.Event(), threading.Event()
    expected = ReplayEventsResult(False, 42, [])

    def blocked_read(*args):
        entered.set()
        assert release.wait(5)
        return expected

    with (
        patch.object(replay, "_read_replay_events", side_effect=blocked_read) as read,
        patch.object(
            replay_executor._threads, "submit", wraps=replay_executor._threads.submit
        ) as submit,
    ):
        first = asyncio.create_task(replay.get_replay_events_result(1, [], 1, None))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            if stop == "deadline":
                monkeypatch.setattr(replay, "REPLAY_TIMEOUT_SECONDS", 0.02)
            for _ in range(5):
                queued = asyncio.create_task(
                    replay.get_replay_events_result(2, [], 1, None)
                )
                await wait_for_queue_size(replay_executor, 1)
                if stop == "cancel":
                    queued.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await queued
                else:
                    assert (await queued).retry_after_ms == 1000
                assert not replay_executor._waiters
                assert replay_executor._active == 1
            assert read.call_count == submit.call_count == 1
        finally:
            release.set()
            assert await first == expected
            await finish_pending_replays()


@pytest.mark.asyncio
@pytest.mark.parametrize("delivered", [True, False])
async def test_cancellation_during_slot_handoff_does_not_leak_capacity(
    replay_executor, delivered
):
    reservation = await replay_executor.acquire()
    queued = asyncio.create_task(replay_executor.acquire())
    await wait_for_queue_size(replay_executor, 1)
    # _release removes the waiter before its delivery runs on the event loop.
    reservation.release()
    if delivered:
        # Delivery runs first, but cancellation precedes the awaiter's next step.
        asyncio.get_running_loop().call_soon(queued.cancel)
    else:
        queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    await asyncio.sleep(0)
    assert replay_executor._active == 0
    next_reservation = await replay_executor.acquire()
    next_reservation.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("live_waiters", [0, 2])
async def test_closed_waiter_loops_preserve_capacity_and_live_fifo(
    replay_executor, live_waiters
):
    reservation = await replay_executor.acquire()
    replay_executor.max_pending = 4
    closed_loop = asyncio.new_event_loop()
    closed_waiters = [closed_loop.create_future() for _ in range(2)]
    closed_loop.close()
    # These admission Futures survived shutdown of their owning loop.
    replay_executor._waiters.extend(closed_waiters)
    queued = []
    for index in range(live_waiters):
        queued.append(asyncio.create_task(replay_executor.acquire()))
        await wait_for_queue_size(replay_executor, 3 + index)

    reservation.release()

    for index, task in enumerate(queued):
        next_reservation = await asyncio.wait_for(task, timeout=1)
        assert replay_executor._active == 1
        assert all(not later.done() for later in queued[index + 1 :])
        next_reservation.release()
    assert replay_executor._active == 0
    assert not replay_executor._waiters
    next_reservation = await replay_executor.acquire()
    next_reservation.release()


@pytest.mark.asyncio
async def test_child_cancelled_before_submission_releases_reservation(replay_executor):
    create_task = asyncio.create_task

    def cancel_before_start(coroutine):
        task = create_task(coroutine)
        task.cancel()
        return task

    with (
        patch.object(asyncio, "create_task", side_effect=cancel_before_start),
        patch.object(replay, "_read_replay_events") as read,
    ):
        with pytest.raises(asyncio.CancelledError):
            await replay.get_replay_events_result(1, [], 1, None)
        await finish_pending_replays()
        read.assert_not_called()
        assert replay_executor._active == 0


@pytest.mark.asyncio
async def test_replay_executor_releases_capacity_after_submission_failure(
    replay_executor,
):
    replay_executor.shutdown()
    for _ in range(2):
        reservation = await replay_executor.acquire()
        with pytest.raises(RuntimeError, match="cannot schedule new futures"):
            reservation.submit(lambda: None)
    assert replay_executor._active == 0


@pytest.mark.asyncio
async def test_replay_executor_releases_capacity_if_cancelled_before_start(
    replay_executor,
):
    # Hold the submitted work before a worker starts it so cancellation is deterministic.
    with patch.object(ThreadPoolExecutor, "submit", side_effect=lambda *args: Future()):
        reservation = await replay_executor.acquire()
        queued = reservation.submit(lambda: None)
        assert queued.cancel()
        reservation = await replay_executor.acquire()
        assert reservation.submit(lambda: None).cancel()
    assert replay_executor._active == 0


@pytest.mark.asyncio
async def test_missing_replay_cursor_does_not_need_a_database_or_pool():
    with patch.object(replay, "_get_executor") as executor:
        result = await replay.get_replay_events_result(1, [], NO_REPLAY_AVAILABLE, None)
        assert result == ReplayEventsResult(
            True, NO_REPLAY_AVAILABLE, [], refresh_reason="missing_cursor"
        )
        executor.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("sqlstate_attribute", ["pgcode", "sqlstate"])
async def test_database_query_cancellation_is_classified_as_timeout(
    replay_executor, sqlstate_attribute
):
    cause = Exception()
    setattr(cause, sqlstate_attribute, "57014")
    error = OperationalError()
    error.__cause__ = cause
    with (
        patch.object(replay, "_read_replay_events", side_effect=error),
        patch.object(replay, "websocket_replay_requests") as requests,
    ):
        assert (await replay.get_replay_events_result(1, [], 1, None)).force_refresh
        assert requests.add.call_args.args[1]["outcome"] == "query_timeout"


@pytest.mark.asyncio
async def test_database_failure_retries_and_releases_capacity(replay_executor):
    with (
        patch.object(
            replay, "_read_replay_events", side_effect=DatabaseError("private")
        ),
        patch.object(replay, "websocket_replay_requests") as requests,
    ):
        result = await replay.get_replay_events_result(1, [], 1, None)
        assert result == ReplayEventsResult(
            True, NO_REPLAY_AVAILABLE, [], retry_after_ms=1000
        )
        assert requests.add.call_args.args[1]["outcome"] == "database_error"

    expected = ReplayEventsResult(False, 42, [])
    with patch.object(replay, "_read_replay_events", return_value=expected):
        assert await replay.get_replay_events_result(1, [], 1, None) == expected


@pytest.mark.parametrize("database_error", [False, True])
def test_replay_closes_only_its_primary_connection(monkeypatch, database_error):
    primary, replica = Mock(), Mock()

    class Connections(dict):
        def close_all(self):
            for database in self.values():
                database.close()

    monkeypatch.setattr(
        replay, "connections", Connections(default=primary, replica=replica)
    )
    expected = ReplayEventsResult(False, 42, [])
    with (
        patch.object(replay.transaction, "atomic"),
        patch.object(replay.connection, "cursor"),
        patch.object(
            replay.RealtimeEventHandler,
            "get_replay_events_result",
            return_value=expected,
            side_effect=DatabaseError("failed") if database_error else None,
        ),
    ):
        if database_error:
            with pytest.raises(DatabaseError):
                replay._read_replay_events(1, [], 1, None, monotonic() + 3)
        else:
            assert (
                replay._read_replay_events(1, [], 1, None, monotonic() + 3) == expected
            )

    primary.close.assert_called_once_with()
    replica.close.assert_not_called()


def test_expired_replay_budget_does_not_open_a_database_connection():
    with (
        patch.object(replay.transaction, "atomic") as atomic,
        patch.object(replay.connections["default"], "close") as close,
    ):
        with pytest.raises(TimeoutError):
            replay._read_replay_events(1, [], 1, None, monotonic() - 1)
        atomic.assert_not_called()
        close.assert_called_once_with()


def test_postgresql_budget_deducts_time_before_thread_and_during_connection_setup():
    with (
        patch.object(replay, "monotonic", side_effect=[1, 2]),
        patch.object(replay.transaction, "atomic"),
        patch.object(replay.connection, "cursor") as cursor,
        patch.object(replay.connections["default"], "close"),
        patch.object(replay.RealtimeEventHandler, "get_replay_events_result"),
    ):
        replay._read_replay_events(1, [], 1, None, deadline=3)
        assert cursor.return_value.__enter__.return_value.execute.call_args.args[1] == [
            "1000ms",
            "1000ms",
        ]


def test_replay_skips_queries_when_connection_setup_exhausts_budget():
    with (
        patch.object(replay, "monotonic", side_effect=[1, 3]),
        patch.object(replay.transaction, "atomic"),
        patch.object(replay.connection, "cursor") as cursor,
        patch.object(replay.connections["default"], "close"),
        patch.object(replay.RealtimeEventHandler, "get_replay_events_result") as read,
    ):
        with pytest.raises(TimeoutError):
            replay._read_replay_events(1, [], 1, None, deadline=3)
        cursor.return_value.__enter__.return_value.execute.assert_not_called()
        read.assert_not_called()


def test_replay_queue_capacity_only_reports_an_initialized_pool(monkeypatch):
    monkeypatch.setattr(replay, "_executor", None)
    assert replay._observe_queue_capacity(None) == []
    with replay.ReplayExecutor(2, max_pending=8) as executor:
        monkeypatch.setattr(replay, "_executor", executor)
        assert replay._observe_queue_capacity(None)[0].value == 8


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "existing_timeout,expected_timeout",
    [("0", "1s"), ("10ms", "10ms"), ("2s", "1s")],
)
def test_replay_timeout_is_local_and_preserves_stricter_timeout(
    existing_timeout, expected_timeout
):
    def read(*args):
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            assert cursor.fetchone()[0] == expected_timeout
        return ReplayEventsResult(False, 0, [])

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, false)", [existing_timeout]
        )
    try:
        with (
            patch.object(replay.connections["default"], "close") as close,
            # One second spent before thread entry and one on connection setup.
            patch.object(replay, "monotonic", side_effect=[1, 2]),
            patch.object(
                replay.RealtimeEventHandler,
                "get_replay_events_result",
                side_effect=read,
            ),
        ):
            result = replay._read_replay_events(
                1, [], FIRST_CONNECT_CURSOR, None, deadline=3
            )
            assert result == ReplayEventsResult(False, 0, [])
            close.assert_called_once_with()
            # Check before closure so reconnecting cannot hide a leaked timeout.
            with connection.cursor() as cursor:
                cursor.execute("SHOW statement_timeout")
                assert cursor.fetchone()[0] == existing_timeout
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_postgresql_stops_slow_replay_and_closes_connection():
    def slow_query(*args):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_sleep(1)")

    with (
        patch.object(
            replay.RealtimeEventHandler,
            "get_replay_events_result",
            side_effect=slow_query,
        ),
        patch.object(replay, "websocket_replay_database_errors") as errors,
    ):
        with pytest.raises(OperationalError) as exc:
            replay._read_replay_events(
                1, [], FIRST_CONNECT_CURSOR, None, monotonic() + 0.025
            )
        assert exc.value.__cause__.pgcode == "57014"
        assert errors.add.call_args.args[1]["reason"] == "query_timeout"
        assert connection.connection is None


@pytest.mark.django_db(transaction=True)
def test_successful_replay_closes_connection_even_with_persistent_connections(
    monkeypatch,
):
    monkeypatch.setitem(connection.settings_dict, "CONN_MAX_AGE", None)
    result = replay._read_replay_events(
        1, [], FIRST_CONNECT_CURSOR, None, monotonic() + 1
    )
    assert result == ReplayEventsResult(False, 0, [])
    assert connection.connection is None
