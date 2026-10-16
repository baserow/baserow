import threading
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

import pytest
from loguru import logger

from baserow.core.chat_runs.constants import MAX_ACTIVE_RUNS_PER_USER, RUN_RETENTION
from baserow.core.chat_runs.exceptions import ChatRunAlreadyActive, ChatRunLimitReached
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.tasks import prune_chat_runs
from baserow.core.models import Workspace

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("terminal", [False, True])
def test_output_failure_logs_only_run_identity_and_exception_class(
    create_run, mocker, terminal
):
    run = create_run()
    private_content = "private-chat-output-canary"
    private_error = "private-provider-error-canary"
    run.outcome = {"content": private_content}
    mocker.patch(
        "baserow.core.chat_runs.buffer.ChatRunBuffer.append",
        side_effect=RuntimeError(private_error),
    )
    written = []
    sink_id = logger.add(written.append, diagnose=True, backtrace=True)
    try:
        handler = ChatRunHandler()
        if terminal:
            handler._publish_terminal(run)
        else:
            handler._publish(run, [("run.created", {"content": private_content})])
    finally:
        logger.remove(sink_id)
    logged = "".join(written)
    assert str(run.id) in logged
    assert "RuntimeError" in logged
    assert private_content not in logged
    assert private_error not in logged


def test_one_active_run_per_conversation_in_database(create_run):
    run = create_run()
    with pytest.raises(IntegrityError), transaction.atomic():
        ChatRun.objects.create(run_type="fake", chat_id=1, workspace=run.workspace)
    ChatRun.objects.create(run_type="other", chat_id=1, workspace=run.workspace)
    ChatRun.objects.create(
        run_type="fake", chat_id=1, workspace=run.workspace, status="completed"
    )
    with pytest.raises(ChatRunAlreadyActive) as error:
        create_run()
    assert error.value.run_id == run.id


def test_per_user_limit_and_userless_runs(create_run):
    first = create_run()
    for n in range(1, MAX_ACTIVE_RUNS_PER_USER):
        create_run(chat_id=n + 1, user=first.created_by, workspace=first.workspace)
    with pytest.raises(ChatRunLimitReached):
        create_run(chat_id=99, user=first.created_by, workspace=first.workspace)
    ChatRunHandler().create_run("fake", 100, first.workspace, None, {})


@pytest.mark.django_db(transaction=True)
def test_parallel_sends_cannot_bypass_user_limit(create_run):
    first = create_run()
    entered = threading.Event()
    release = threading.Event()
    results = []

    def send(chat_id, hold=False):
        try:
            with transaction.atomic():
                create_run(
                    chat_id=chat_id, user=first.created_by, workspace=first.workspace
                )
                if hold:
                    entered.set()
                    release.wait(10)
                results.append("created")
        except ChatRunLimitReached:
            results.append("limited")
        finally:
            connection.close()

    a = threading.Thread(target=send, args=(2, True))
    b = threading.Thread(target=send, args=(3,))
    a.start()
    try:
        assert entered.wait(10)
        b.start()
        b.join(0.1)
        assert b.is_alive()
    finally:
        release.set()
        a.join(10)
        b.join(10)
    assert results == ["created", "limited"]


def test_start_enqueues_only_after_commit_even_if_output_publication_fails(
    create_run, mocker, django_capture_on_commit_callbacks
):
    existing = create_run()
    enqueue = mocker.patch.object(ChatRunHandler, "_enqueue")
    mocker.patch.object(ChatRunHandler, "_publish", side_effect=ConnectionError)
    mocker.patch("baserow.core.chat_runs.handler.notify_run_on_commit")
    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            run = ChatRunHandler().start_run(
                "fake", 2, existing.workspace, existing.created_by, {}, {}
            )
            enqueue.assert_not_called()
    enqueue.assert_called_once_with(run.id)


def test_claim_once_and_cancel_durably_without_redis(create_run):
    run = create_run()
    handler = ChatRunHandler()
    assert handler.claim_run(run.id) is not None
    assert handler.claim_run(run.id) is None
    assert handler.request_cancel(run.id) == ChatRunStatus.RUNNING
    first = handler.get_run(run.id).cancel_requested_at
    handler.request_cancel(run.id)
    assert handler.get_run(run.id).cancel_requested_at == first
    assert handler.renew_lease(run.id).cancel_requested


def test_queued_stop_is_terminal_and_cannot_be_claimed(create_run):
    run = create_run()
    assert ChatRunHandler().request_cancel(run.id) == ChatRunStatus.CANCELLED
    assert ChatRunHandler().claim_run(run.id) is None


def test_terminal_outcome_cannot_be_overwritten(create_run):
    run = create_run(claim=True)
    handler = ChatRunHandler()
    assert handler.finish_run(run.id, "completed", message={"id": 15})
    assert not handler.finish_run(run.id, "failed", "interrupted", {"id": 16})
    run.refresh_from_db()
    assert run.outcome == {"id": 15}
    assert run.status == "completed"


@pytest.mark.parametrize(
    "redis_events",
    [None, [{"kind": "text.delta", "data": {"text": "hi", "segment": 0}}]],
)
def test_expired_worker_ends_with_or_without_output(
    create_run, fake_run_type, mocker, redis_events
):
    run = create_run(claim=True)
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    mocker.patch.object(ChatRunHandler, "_recover_output", return_value=redis_events)
    assert ChatRunHandler().finalize_lost_runs() == 1
    run.refresh_from_db()
    assert (run.status, run.error_code) == ("failed", "interrupted")
    assert fake_run_type.lost_events == [redis_events]
    assert fake_run_type.executed == 0


def test_recovery_rechecks_lease_after_reading_output(
    create_run, fake_run_type, mocker
):
    run = create_run(claim=True)
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )

    def read(run_id):
        ChatRunHandler().renew_lease(run_id)
        return []

    mocker.patch.object(ChatRunHandler, "_recover_output", side_effect=read)
    assert ChatRunHandler().finalize_lost_runs() == 0
    assert fake_run_type.lost_events == []


def test_failing_recovery_hook_rolls_back_product_writes_but_ends_run(
    create_run, fake_run_type, mocker
):
    run = create_run(claim=True)
    name = run.workspace.name
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    mocker.patch.object(ChatRunHandler, "_recover_output", return_value=None)

    def fail(run, events):
        Workspace.objects.filter(id=run.workspace_id).update(name="wrong")
        raise RuntimeError()

    fake_run_type.on_run_lost = fail
    assert ChatRunHandler().finalize_lost_runs() == 1
    run.refresh_from_db()
    assert run.outcome is None
    assert run.error_code == "interrupted"
    assert Workspace.objects.get(id=run.workspace_id).name == name


def test_pruning_keeps_started_incomplete_turn_until_warning_is_preserved(
    create_run, fake_run_type
):
    run = create_run(claim=True)
    ChatRunHandler().finish_run(run.id, "failed", "persist_failed")
    ChatRun.objects.filter(id=run.id).update(
        finished_on=timezone.now() - RUN_RETENTION - timedelta(days=1)
    )
    ChatRunHandler().prune()
    assert ChatRun.objects.filter(id=run.id).exists()
    fake_run_type.warnings_preserved = True
    ChatRunHandler().prune()
    assert not ChatRun.objects.filter(id=run.id).exists()


def test_pruning_continues_past_retained_rows_with_a_fixed_cutoff(
    create_run, data_fixture, mocker, monkeypatch
):
    monkeypatch.setattr("baserow.core.chat_runs.handler.SWEEP_BATCH_SIZE", 2)
    enqueue = mocker.patch.object(prune_chat_runs, "delay")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    expired = timezone.now() - RUN_RETENTION - timedelta(days=1)
    retained = []
    for index in range(5):
        run = create_run(chat_id=index, user=user, workspace=workspace, claim=True)
        ChatRunHandler().finish_run(run.id, "failed" if index < 2 else "completed")
        ChatRun.objects.filter(id=run.id).update(
            finished_on=expired + timedelta(seconds=index >= 2)
        )
        if index < 2:
            retained.append(run.id)
    recent = create_run(chat_id=6, user=user, workspace=workspace, claim=True)
    ChatRunHandler().finish_run(recent.id, "completed")

    prune_chat_runs()
    enqueue.assert_called_once()
    first_continuation = enqueue.call_args.kwargs
    cutoff = first_continuation["before"]
    calls = 1
    while enqueue.called:
        continuation = enqueue.call_args.kwargs
        assert continuation["before"] == cutoff
        enqueue.reset_mock()
        prune_chat_runs(**continuation)
        calls += 1
        assert calls <= 3

    assert calls == 3
    assert set(ChatRun.objects.values_list("id", flat=True)) == {*retained, recent.id}


@pytest.mark.django_db(transaction=True)
def test_recovery_reads_redis_before_opening_transaction(create_run, mocker):
    run = create_run(claim=True)
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )

    def recover(run_id):
        assert not connection.in_atomic_block
        return None

    mocker.patch.object(ChatRunHandler, "_recover_output", side_effect=recover)
    assert ChatRunHandler().finalize_lost_runs() == 1


@pytest.mark.django_db(transaction=True)
def test_only_one_finalizer_saves_product_changes(create_run, fake_run_type, mocker):
    from baserow.core.chat_runs.runner import _finish
    from baserow.core.chat_runs.types import ChatRunOutcome

    run = create_run(claim=True)
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    mocker.patch.object(ChatRunHandler, "_recover_output", return_value=None)
    mocker.patch.object(ChatRunHandler, "_publish_terminal")
    locked = threading.Event()
    release = threading.Event()
    outcomes = {}

    def save_lost(run, events):
        locked.set()
        assert release.wait(10)
        Workspace.objects.filter(id=run.workspace_id).update(name="Recovered")
        return {"content": "interrupted"}

    fake_run_type.on_run_lost = save_lost

    def sweep():
        try:
            outcomes["sweeper"] = ChatRunHandler().finalize_lost_runs()
        finally:
            connection.close()

    def finish():
        try:
            outcomes["worker"] = _finish(
                fake_run_type,
                run,
                ChatRunOutcome(ChatRunStatus.COMPLETED, result="late"),
            )
        finally:
            connection.close()

    sweeper = threading.Thread(target=sweep)
    worker = threading.Thread(target=finish)
    sweeper.start()
    try:
        assert locked.wait(10)
        worker.start()
        worker.join(0.1)
        assert worker.is_alive()
    finally:
        release.set()
        sweeper.join(10)
        worker.join(10)
    assert outcomes == {"sweeper": 1, "worker": None}
    assert fake_run_type.persisted == []
    run.refresh_from_db()
    assert run.outcome == {"content": "interrupted"}
    assert Workspace.objects.get(id=run.workspace_id).name == "Recovered"


def test_failed_enqueue_ends_only_unclaimed_work(create_run, mocker):
    mocker.patch(
        "baserow.core.chat_runs.tasks.execute_chat_run.delay",
        side_effect=ConnectionError,
    )
    queued = create_run(chat_id=1)
    claimed = create_run(chat_id=2, claim=True)
    ChatRunHandler()._enqueue(queued.id)
    ChatRunHandler()._enqueue(claimed.id)
    queued.refresh_from_db()
    claimed.refresh_from_db()
    assert (queued.status, queued.error_code) == ("failed", "not_started")
    assert claimed.status == "running"
