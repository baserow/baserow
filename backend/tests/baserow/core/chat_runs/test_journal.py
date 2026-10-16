import asyncio
import threading
from contextlib import suppress
from types import SimpleNamespace
from uuid import uuid4

import pytest

from baserow.core.chat_runs import journal as journal_module
from baserow.core.chat_runs.constants import STOP_CANCELLED
from baserow.core.chat_runs.journal import ChatRunJournal, coalesce_events


def test_coalescing_preserves_rewrites_and_product_event_order():
    events = [
        ("progress", {"text": "Reading"}),
        ("text.delta", {"segment": 0, "text": "Hel"}),
        ("progress", {"text": "Writing"}),
        ("text.delta", {"segment": 0, "text": "lo"}),
        ("navigation", {"location": "table"}),
        ("text.delta", {"segment": 1, "text": "New"}),
    ]
    assert coalesce_events(events) == [
        ("text.delta", {"segment": 0, "text": "Hello"}),
        ("progress", {"text": "Writing"}),
        ("navigation", {"location": "table"}),
        ("text.delta", {"segment": 1, "text": "New"}),
    ]


@pytest.mark.asyncio
async def test_text_rewrites_are_new_segments_and_nuls_are_removed(output_buffer):
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))
    for text in ["Hel", "Hello", "Hello", "Bye\x00", "By", "By now"]:
        journal.emit_text(text)
    await journal.flush()
    assert output_buffer.append.await_args.args[0] == [
        ("text.delta", {"segment": 0, "text": "Hello"}),
        ("text.delta", {"segment": 1, "text": "Bye"}),
        ("text.delta", {"segment": 2, "text": "By now"}),
    ]


@pytest.mark.asyncio
async def test_output_failure_drops_bounded_queue_without_stopping_or_retrying(
    output_buffer,
):
    output_buffer.append.side_effect = TimeoutError()
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))
    journal.emit_text("answer")
    await journal.flush()
    journal.emit_text("answer continues")
    journal.emit("navigation", {"location": "table"})
    await journal.flush()
    await journal.publish_finished(
        {"status": "completed", "message": {"content": "final answer"}}
    )
    assert journal.output_unavailable
    assert not journal.stop_requested.is_set()
    assert journal._pending == []
    assert journal._text == ""
    output_buffer.append.assert_awaited_once()
    output_buffer.invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_output_limits_do_not_limit_execution(output_buffer, monkeypatch):
    monkeypatch.setattr(journal_module, "MAX_PENDING_BYTES", 50)
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))
    journal.emit_text("x" * 100)
    await journal.flush()
    assert journal.output_unavailable
    assert not journal.stop_requested.is_set()
    output_buffer.append.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_thread_callback_backlog_is_bounded(output_buffer, monkeypatch):
    monkeypatch.setattr(journal_module, "MAX_PENDING_EVENTS", 3)
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))

    def flood():
        for index in range(100):
            journal.emit("progress", {"index": index})

    thread = threading.Thread(target=flood)
    thread.start()
    thread.join()
    assert len(journal._thread_pending) <= 3
    await asyncio.sleep(0)
    assert journal.output_unavailable
    assert not journal.stop_requested.is_set()


@pytest.mark.asyncio
async def test_lease_stop_polling_proceeds_while_output_append_waits(
    output_buffer, monkeypatch
):
    monkeypatch.setattr(journal_module, "LEASE_RENEW_INTERVAL_SECONDS", 0.005)
    waiting = asyncio.Event()

    async def stalled_append(*args):
        waiting.set()
        await asyncio.Event().wait()

    output_buffer.append.side_effect = stalled_append
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(
        journal,
        "_renew_lease",
        lambda: SimpleNamespace(alive=True, cancel_requested=True),
    )
    journal.emit_text("partial")
    flush = asyncio.create_task(journal.flush())
    keeper = asyncio.create_task(journal.keep_alive())
    await waiting.wait()
    assert await asyncio.wait_for(journal.wait_for_stop(), 0.5) == STOP_CANCELLED
    for task in [flush, keeper]:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_finished_publishes_committed_snapshot_then_sets_reconnect_ttl(
    output_buffer,
):
    journal = ChatRunJournal(SimpleNamespace(id=uuid4()))
    snapshot = {"status": "completed", "message": {"id": 3}}
    await journal.publish_finished(snapshot)
    output_buffer.append.assert_awaited_once_with([("run.finished", snapshot)])
    output_buffer.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_overflow_marks_healthy_redis_replay_unavailable(monkeypatch):
    from baserow.core.chat_runs.buffer import ChatRunBuffer, ReplayUnavailable

    run = SimpleNamespace(id=uuid4())
    journal = ChatRunJournal(run)
    journal.emit("run.started")
    journal.emit_text("prefix")
    await journal.flush()
    monkeypatch.setattr(journal_module, "MAX_PENDING_BYTES", 20)
    journal.emit_text("prefix" + "x" * 100)
    await journal.flush()
    with pytest.raises(ReplayUnavailable, match="unavailable"):
        await ChatRunBuffer(run.id).read()
    assert not journal.stop_requested.is_set()
