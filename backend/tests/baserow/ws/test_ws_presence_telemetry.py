import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, call

import pytest
from asgiref.sync import SyncToAsync

from baserow.ws import telemetry
from baserow.ws.presence import PresenceHandler
from baserow.ws.registries import page_registry


@pytest.fixture
def presence_sync_metrics(monkeypatch):
    metrics = {}
    for name in (
        "websocket_sync_queue_duration",
        "websocket_sync_execution_duration",
        "websocket_sync_pending",
        "websocket_sync_executing",
    ):
        metrics[name] = MagicMock()
        monkeypatch.setattr(telemetry, name, metrics[name])
    return metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_resolution", [False, True])
async def test_presence_resolution_measures_shared_queue_and_execution(
    monkeypatch, presence_sync_metrics, fail_resolution
):
    now = [0.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])
    loop = asyncio.get_running_loop()
    blocker_started = asyncio.Event()
    release_blocker = threading.Event()

    def block_executor():
        loop.call_soon_threadsafe(blocker_started.set)
        assert release_blocker.wait(5)

    def cleanup():
        now[0] += 0.1

    monkeypatch.setattr("channels.db.close_old_connections", cleanup)
    page_type = page_registry.get("table")
    resolve = page_type.get_presence_space_name

    def timed_resolve(**parameters):
        now[0] += 0.05
        if fail_resolution:
            raise ValueError("presence resolution failed")
        return resolve(**parameters)

    monkeypatch.setattr(page_type, "get_presence_space_name", timed_resolve)
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(SyncToAsync, "single_thread_executor", executor)
        blocker = executor.submit(block_executor)
        try:
            await asyncio.wait_for(blocker_started.wait(), 2)
            task = asyncio.create_task(
                PresenceHandler.resolve_space_name("table", {"table_id": 12345})
            )
            await asyncio.sleep(0)
            now[0] += 0.25
            release_blocker.set()
            if fail_resolution:
                with pytest.raises(ValueError, match="presence resolution failed"):
                    await asyncio.wait_for(task, 2)
            else:
                assert await asyncio.wait_for(task, 2) == "table-12345"
        finally:
            release_blocker.set()
        blocker.result()

    attributes = {
        "operation": "presence_space",
        "executor": "thread_sensitive",
        "process.pid": os.getpid(),
    }
    presence_sync_metrics[
        "websocket_sync_queue_duration"
    ].record.assert_called_once_with(250.0, attributes)
    # Both database connection cleanups remain part of execution, including when
    # a page callback fails. Page names and subscription parameters are not labels.
    presence_sync_metrics[
        "websocket_sync_execution_duration"
    ].record.assert_called_once_with(
        pytest.approx(250.0),
        {**attributes, "outcome": "error" if fail_resolution else "success"},
    )
    for name in ("websocket_sync_pending", "websocket_sync_executing"):
        assert presence_sync_metrics[name].add.call_args_list == [
            call(1, attributes),
            call(-1, attributes),
        ]


@pytest.mark.asyncio
async def test_unknown_presence_page_does_not_submit_sync_work(presence_sync_metrics):
    assert (
        await PresenceHandler.resolve_space_name(
            "unknown-client-provided-page", {"slug": "private-subscription"}
        )
        is None
    )
    for metric in presence_sync_metrics.values():
        assert metric.mock_calls == []
