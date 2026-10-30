import asyncio
from contextlib import aclosing
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from baserow.core.chat_runs import stream
from baserow.core.chat_runs.buffer import (
    MAX_BUFFER_EVENTS,
    ChatRunBuffer,
    ReplayUnavailable,
)
from baserow.core.chat_runs.stream import follow_run


@pytest.mark.asyncio
async def test_resume_baseline_survives_appends_and_suppresses_catchup_effects(
    buffer_redis, monkeypatch
):
    run = SimpleNamespace(id=uuid4())
    writer = ChatRunBuffer(run.id)
    prefix = await writer.append(
        [
            ("run.started", {}),
            ("text.delta", {"segment": 0, "text": "Hello"}),
        ]
    )
    await writer.append(
        [
            ("navigation", {"location": "table"}),
            ("text.delta", {"segment": 0, "text": " there"}),
        ]
    )
    original_xrange = buffer_redis.xrange
    appended = False

    async def append_during_reconstruction(*args, **kwargs):
        nonlocal appended
        rows = await original_xrange(*args, **kwargs)
        if kwargs.get("count") == MAX_BUFFER_EVENTS + 1 and not appended:
            appended = True
            await writer.append([("text.delta", {"segment": 0, "text": " live"})])
        return rows

    monkeypatch.setattr(buffer_redis, "xrange", append_during_reconstruction)
    follower = follow_run(
        run,
        None,
        prefix[-1]["cursor"],
        snapshot=AsyncMock(return_value={"status": "running"}),
    )
    async with aclosing(follower):
        baseline = await anext(follower)
        navigation = await anext(follower)
        text = await anext(follower)
        assert baseline["kind"] == "run.baseline"
        assert baseline["data"]["text"] == "Hello"
        assert baseline["cursor"] == prefix[-1]["cursor"]
        assert navigation["kind"] == "navigation"
        assert navigation["replayed"]
        assert text["data"]["text"] == " there"
        assert text["replayed"]
        concurrent = await anext(follower)
        assert concurrent["data"]["text"] == " live"
        assert not concurrent["replayed"]
        await writer.append([("navigation", {"location": "new-table"})])
        live = await anext(follower)
        assert live["kind"] == "navigation"
        assert not live["replayed"]


@pytest.mark.asyncio
async def test_new_send_treats_its_own_fast_worker_output_as_live():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [("run.started", {}), ("navigation", {"location": "table"})]
    )
    follower = follow_run(
        run, None, replay=False, snapshot=AsyncMock(return_value={"status": "running"})
    )
    async with aclosing(follower):
        assert not (await anext(follower))["replayed"]
        assert not (await anext(follower))["replayed"]


@pytest.mark.asyncio
async def test_live_output_skips_saved_state_reads(monkeypatch):
    monkeypatch.setattr(stream, "STATUS_INTERVAL_SECONDS", 0.2)
    run = SimpleNamespace(id=uuid4())
    writer = ChatRunBuffer(run.id)
    await writer.append([("run.started", {})])
    snapshot = AsyncMock(return_value={"status": "running"})
    follower = follow_run(run, None, replay=False, snapshot=snapshot)
    async with aclosing(follower):
        assert (await anext(follower))["kind"] == "run.started"
        for _ in range(6):
            await writer.append([("text.delta", {"segment": 0, "text": "x"})])
            assert (await anext(follower))["kind"] == "text.delta"
            await asyncio.sleep(0.05)
        assert snapshot.await_count == 1


@pytest.mark.asyncio
async def test_missing_replay_waits_for_durable_outcome_without_reexecuting(
    monkeypatch,
):
    monkeypatch.setattr(stream, "STATUS_INTERVAL_SECONDS", 0.001)
    run = SimpleNamespace(id=uuid4())
    snapshot = AsyncMock(
        side_effect=[
            {"status": "running"},
            {"status": "completed", "message": {"id": 7, "content": "answer"}},
        ]
    )
    cursor = f"{uuid4().hex}:1-0"
    records = [
        record async for record in follow_run(run, None, cursor, snapshot=snapshot)
    ]
    assert [record["kind"] for record in records] == [
        "run.replay_unavailable",
        "run.finished",
    ]
    assert records[-1]["data"]["message"]["id"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resume,error", [(False, ReplayUnavailable("missing")), (True, ConnectionError())]
)
async def test_transient_output_failure_is_retried_without_a_notice(
    monkeypatch, resume, error
):
    monkeypatch.setattr(stream, "STATUS_INTERVAL_SECONDS", 0.01)
    run = SimpleNamespace(id=uuid4())
    started = await ChatRunBuffer(run.id).append([("run.started", {})])
    await ChatRunBuffer(run.id).append([("text.delta", {"segment": 1, "text": "Hi"})])
    read, failures = ChatRunBuffer.read, [error]

    async def fail_once(self, *args, **kwargs):
        if failures:
            raise failures.pop()
        return await read(self, *args, **kwargs)

    monkeypatch.setattr(ChatRunBuffer, "read", fail_once)
    cursor = started[-1]["cursor"] if resume else None
    snapshot = AsyncMock(return_value={"status": "running"})
    async with aclosing(follow_run(run, None, cursor, snapshot=snapshot)) as follower:
        records = [await anext(follower) for _ in range(3)]
    assert records[0]["kind"] == "run.heartbeat"
    assert records[-1]["data"]["text"] == "Hi"


@pytest.mark.asyncio
async def test_durable_terminal_wins_over_late_redis_output():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [("run.started", {}), ("text.delta", {"segment": 0, "text": "stale"})]
    )
    records = [
        record
        async for record in follow_run(
            run,
            None,
            snapshot=AsyncMock(
                return_value={
                    "status": "failed",
                    "error_code": "interrupted",
                    "message": None,
                }
            ),
        )
    ]
    assert len(records) == 1
    assert records[0]["kind"] == "run.finished"
    assert records[0]["data"]["error_code"] == "interrupted"


@pytest.mark.asyncio
async def test_finished_notification_is_checked_against_durable_state():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [
            ("run.started", {}),
            (
                "run.finished",
                {"status": "completed", "message": {"content": "untrusted"}},
            ),
        ]
    )
    snapshot = AsyncMock(
        side_effect=[
            {"status": "running"},
            {"status": "failed", "message": {"content": "committed"}},
        ]
    )
    records = [record async for record in follow_run(run, None, snapshot=snapshot)]
    assert records[-1]["data"]["status"] == "failed"
    assert records[-1]["data"]["message"]["content"] == "committed"
