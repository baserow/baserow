import asyncio

from django.db import connection

import pytest
from asgiref.sync import async_to_sync

from baserow.core.chat_runs.constants import STOP_CANCELLED
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.runner import run_chat_run
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.models import Workspace

pytestmark = pytest.mark.django_db


def test_task_claims_once_and_persists_only_final_output(
    create_run, fake_run_type, output_buffer
):
    run = create_run()
    execute_chat_run(str(run.id))
    execute_chat_run(str(run.id))
    run.refresh_from_db()
    assert fake_run_type.executed == 1
    assert run.status == "completed"
    assert run.outcome["content"] == "Hello"
    assert len(fake_run_type.persisted) == 1


def test_redis_failure_does_not_prevent_durable_completion(
    create_run, fake_run_type, output_buffer
):
    output_buffer.append.side_effect = ConnectionError("output buffer down")
    run = create_run()
    execute_chat_run(str(run.id))
    run.refresh_from_db()
    assert run.status == "completed"
    assert run.outcome["content"] == "Hello"
    assert fake_run_type.executed == 1


@pytest.mark.django_db(transaction=True)
def test_completion_is_published_only_after_final_database_commit(
    create_run, fake_run_type, output_buffer, mocker
):
    run = create_run(claim=True)
    observed = []

    async def published(snapshot):
        # This hook runs after _finish returns from its transaction.
        from asgiref.sync import sync_to_async

        def read():
            assert not connection.in_atomic_block
            return ChatRun.objects.get(id=run.id).outcome

        observed.append(await sync_to_async(read)())

    mocker.patch(
        "baserow.core.chat_runs.journal.ChatRunJournal.publish_finished",
        side_effect=published,
    )
    async_to_sync(run_chat_run)(run, fake_run_type)
    assert observed == [{"id": 17, "type": "ai/message", "content": "Hello"}]


def test_failed_product_persistence_rolls_back_and_preserves_started_warning(
    create_run, fake_run_type, output_buffer
):
    run = create_run(claim=True)
    name = run.workspace.name

    def fail(run, outcome):
        Workspace.objects.filter(id=run.workspace_id).update(name="wrong")
        raise RuntimeError("cannot save answer")

    warnings = []
    fake_run_type.persist_outcome = fail
    fake_run_type.ensure_interruption_warning = lambda run: (
        warnings.append(run.started_on) or True
    )
    async_to_sync(run_chat_run)(run, fake_run_type)
    run.refresh_from_db()
    assert (run.status, run.error_code, run.outcome) == (
        "failed",
        "persist_failed",
        None,
    )
    assert warnings == [run.started_on]
    assert Workspace.objects.get(id=run.workspace_id).name == name


def test_stale_worker_cannot_save_over_sweeper_winner(
    create_run, fake_run_type, output_buffer
):
    run = create_run(claim=True)
    ChatRunHandler().finish_run(run.id, "failed", "interrupted", {"content": "lost"})
    async_to_sync(run_chat_run)(run, fake_run_type)
    run.refresh_from_db()
    assert run.outcome == {"content": "lost"}
    assert fake_run_type.persisted == []


@pytest.mark.django_db(transaction=True)
def test_stop_polling_continues_while_redis_append_blocks(
    create_run, fake_run_type, output_buffer, monkeypatch
):
    run = create_run(claim=True)
    monkeypatch.setattr(
        "baserow.core.chat_runs.journal.LEASE_RENEW_INTERVAL_SECONDS", 0.01
    )
    entered = asyncio.Event()

    async def append(*args):
        entered.set()
        await asyncio.sleep(0.1)
        raise ConnectionError()

    output_buffer.append.side_effect = append

    async def execute(run, journal):
        journal.emit_text("working")
        journal.emit("progress", {"text": "working"}, flush_now=True)
        from asgiref.sync import sync_to_async

        await entered.wait()
        await sync_to_async(ChatRunHandler().request_cancel)(run.id)
        reason = await asyncio.wait_for(journal.wait_for_stop(), 1)
        assert reason == STOP_CANCELLED
        return ChatRunOutcome(ChatRunStatus.CANCELLED, result="partial")

    fake_run_type.execute = execute
    async_to_sync(run_chat_run)(run, fake_run_type)
    run.refresh_from_db()
    assert run.status == "cancelled"
    assert run.outcome["content"] == "partial"
