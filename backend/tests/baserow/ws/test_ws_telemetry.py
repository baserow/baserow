import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from baserow.ws import replay, telemetry
from baserow.ws.auth import ANONYMOUS_USER_TOKEN, get_user


@pytest.fixture
def telemetry_metrics(monkeypatch):
    metrics = {}
    for name in (
        "websocket_sync_queue_duration",
        "websocket_sync_execution_duration",
        "websocket_sync_pending",
        "websocket_sync_executing",
        "websocket_phase_duration",
        "websocket_handshakes_pending",
        "websocket_event_loop_lag",
    ):
        metrics[name] = MagicMock()
        monkeypatch.setattr(telemetry, name, metrics[name])
    return metrics


@pytest.mark.asyncio
async def test_sync_telemetry_separates_executor_queue_and_execution(
    monkeypatch, telemetry_metrics
):
    now = [0.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])
    loop = asyncio.get_running_loop()
    blocker_started = asyncio.Event()
    release_blocker = threading.Event()

    def block_executor():
        loop.call_soon_threadsafe(blocker_started.set)
        assert release_blocker.wait(5)

    def operation():
        now[0] += 0.05
        return "result"

    with ThreadPoolExecutor(max_workers=1) as executor:
        blocker = executor.submit(block_executor)
        try:
            await asyncio.wait_for(blocker_started.wait(), 2)
            task = asyncio.create_task(
                telemetry.run_sync("replay", operation, executor=executor)
            )
            await asyncio.sleep(0)
            now[0] += 0.25
            release_blocker.set()
            assert await asyncio.wait_for(task, 2) == "result"
        finally:
            release_blocker.set()
        blocker.result()

    attributes = {
        "operation": "replay",
        "executor": "isolated",
        "process.pid": os.getpid(),
    }
    telemetry_metrics["websocket_sync_queue_duration"].record.assert_called_once_with(
        250.0, attributes
    )
    telemetry_metrics[
        "websocket_sync_execution_duration"
    ].record.assert_called_once_with(
        pytest.approx(50.0), {**attributes, "outcome": "success"}
    )
    for name in ("websocket_sync_pending", "websocket_sync_executing"):
        assert telemetry_metrics[name].add.call_args_list == [
            call(1, attributes),
            call(-1, attributes),
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_sync_telemetry_counts_database_cleanup_as_execution(
    monkeypatch, telemetry_metrics, fail_cleanup
):
    now = [0.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])

    def cleanup():
        now[0] += 0.1
        if fail_cleanup:
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr("channels.db.close_old_connections", cleanup)

    def operation():
        now[0] += 0.05
        return 42

    if fail_cleanup:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            await telemetry.run_database_sync("authentication", operation)
    else:
        assert await telemetry.run_database_sync("authentication", operation) == 42

    attributes = {
        "operation": "authentication",
        "executor": "thread_sensitive",
        "process.pid": os.getpid(),
    }
    telemetry_metrics["websocket_sync_queue_duration"].record.assert_called_once_with(
        0.0, attributes
    )
    telemetry_metrics[
        "websocket_sync_execution_duration"
    ].record.assert_called_once_with(
        pytest.approx(100.0 if fail_cleanup else 250.0),
        {**attributes, "outcome": "error" if fail_cleanup else "success"},
    )
    assert telemetry_metrics["websocket_sync_executing"].add.call_args_list == [
        call(1, attributes),
        call(-1, attributes),
    ]


@pytest.mark.asyncio
async def test_cancelled_sync_caller_does_not_hide_executing_work(telemetry_metrics):
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()

    def operation():
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        task = asyncio.create_task(
            telemetry.run_sync("replay", operation, executor=executor)
        )
        try:
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            # The coroutine has left, but its synchronous operation still occupies
            # the executor. The two gauges deliberately describe different things.
            pending = telemetry_metrics["websocket_sync_pending"].add.call_args_list
            executing = telemetry_metrics["websocket_sync_executing"].add.call_args_list
            assert [entry.args[0] for entry in pending] == [1, -1]
            assert [entry.args[0] for entry in executing] == [1]
        finally:
            release.set()
    executing = telemetry_metrics["websocket_sync_executing"].add.call_args_list
    assert [entry.args[0] for entry in executing] == [1, -1]


@pytest.mark.asyncio
async def test_anonymous_auth_does_not_submit_executor_work(monkeypatch, settings):
    run = AsyncMock(side_effect=AssertionError("anonymous auth queued sync work"))
    monkeypatch.setattr("baserow.ws.auth.run_database_sync", run)
    settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS = False
    assert (await get_user(ANONYMOUS_USER_TOKEN)).is_anonymous
    settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS = True
    assert await get_user(ANONYMOUS_USER_TOKEN) is None
    run.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["accepted", "rejected", "error", "cancelled"])
async def test_handshake_telemetry_balances_pending_and_cleans_up(
    monkeypatch, telemetry_metrics, outcome
):
    now = [0.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])
    original_connection_id = telemetry._connection_id.get()
    connection_ids = []

    async def inner(scope, receive, send):
        connection_ids.append(telemetry._connection_id.get())
        now[0] += 0.25
        if outcome == "accepted":
            await send({"type": "websocket.accept"})
            now[0] += 20
            await send({"type": "websocket.close"})
        elif outcome == "rejected":
            await send({"type": "websocket.close"})
        elif outcome == "error":
            raise ValueError("handshake failed")
        else:
            raise asyncio.CancelledError

    app = telemetry.WebsocketTelemetryMiddleware(inner)
    scope = {"query_string": b"jwt_token=secret&web_socket_id=client-controlled"}
    if outcome in {"accepted", "rejected"}:
        await app(scope, AsyncMock(), AsyncMock())
    else:
        with pytest.raises(
            ValueError if outcome == "error" else asyncio.CancelledError
        ):
            await app(scope, AsyncMock(), AsyncMock())

    attributes = {"process.pid": os.getpid()}
    assert telemetry_metrics["websocket_handshakes_pending"].add.call_args_list == [
        call(1, attributes),
        call(-1, attributes),
    ]
    phases = telemetry_metrics["websocket_phase_duration"].record.call_args_list
    handshake_phases = [
        entry for entry in phases if entry.args[1]["phase"] == "handshake"
    ]
    assert handshake_phases == [
        call(250.0, {**attributes, "phase": "handshake", "outcome": outcome})
    ]
    assert len(connection_ids[0]) == 32
    assert telemetry._connection_id.get() == original_connection_id
    assert asyncio.get_running_loop() not in telemetry._event_loop_monitors


@pytest.mark.asyncio
async def test_concurrent_websockets_share_one_loop_monitor(telemetry_metrics):
    entered = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]
    monitor_states = []

    async def inner(scope, receive, send):
        index = scope["index"]
        monitor = telemetry._event_loop_monitors[asyncio.get_running_loop()]
        monitor_states.append((monitor, monitor.handle))
        entered[index].set()
        await release[index].wait()

    app = telemetry.WebsocketTelemetryMiddleware(inner)
    tasks = []
    try:
        for index in range(2):
            tasks.append(
                asyncio.create_task(app({"index": index}, AsyncMock(), AsyncMock()))
            )
            await asyncio.wait_for(entered[index].wait(), 2)
        assert monitor_states[0] == monitor_states[1]
        monitor, handle = monitor_states[0]
        assert monitor.connections == 2
        release[0].set()
        await tasks[0]
        assert monitor.connections == 1
        assert not handle.cancelled()
        release[1].set()
        await tasks[1]
        assert handle.cancelled()
        assert monitor.connections == 0
    finally:
        for event in release:
            event.set()
        await asyncio.gather(*tasks)


def test_event_loop_monitor_measures_scheduling_delay(telemetry_metrics):
    loop = MagicMock()
    loop.time.return_value = 1.0
    monitor = telemetry._EventLoopMonitor(loop)
    monitor.acquire()
    loop.call_at.assert_called_once_with(2.0, monitor._tick)
    loop.time.return_value = 2.25
    monitor._tick()
    telemetry_metrics["websocket_event_loop_lag"].record.assert_called_once_with(
        250.0, {"process.pid": os.getpid()}
    )
    assert loop.call_at.call_count == 2
    monitor.release()


@pytest.mark.asyncio
async def test_sync_operation_labels_are_bounded(telemetry_metrics):
    assert await telemetry.run_sync("client-controlled-name", lambda: 42) == 42
    attributes = telemetry_metrics[
        "websocket_sync_queue_duration"
    ].record.call_args.args[1]
    assert attributes["operation"] == "other"


def test_slow_logs_are_rate_limited_and_correlate_without_client_data(monkeypatch):
    monkeypatch.setattr(telemetry, "_last_slow_log", {})
    logger = MagicMock()
    monkeypatch.setattr(telemetry, "logger", logger)
    now = [100.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])

    telemetry._log_slow("queue", "replay", 0.1, "server-generated-id")
    telemetry._log_slow("queue", "replay", 2.0, "server-generated-id")
    telemetry._log_slow("queue", "replay", 3.0, "another-generated-id")
    assert logger.warning.call_count == 1
    assert logger.warning.call_args.args[-1] == "server-generated-id"
    now[0] += 30
    telemetry._log_slow("queue", "replay", 3.0, "another-generated-id")
    assert logger.warning.call_count == 2


def test_replay_capacity_excludes_processes_without_an_initialized_pool(monkeypatch):
    monkeypatch.setattr(replay, "_executor", None)
    assert replay._observe_capacity(None) == []

    with replay.ReplayExecutor(2) as executor:
        monkeypatch.setattr(replay, "_executor", executor)
        observations = replay._observe_capacity(None)
        assert len(observations) == 1
        assert observations[0].value == 2
        assert observations[0].attributes == {"process.pid": os.getpid()}
