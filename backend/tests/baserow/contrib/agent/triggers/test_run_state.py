from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import connection, transaction
from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.constants import AGENT_RUN_TYPE
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentConversation,
    AgentMessage,
    AgentTrigger,
)
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.tasks import start_queued_trigger_replies
from baserow.contrib.agent.triggers.handler import AgentTriggerHandler
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.trash.handler import TrashHandler

from ..utils import (
    hold_a_workspace_run,
    in_another_connection,
    queued_reply,
    wait_for_a_lock_waiter,
)


def trigger_reply(
    data_fixture,
    trigger: AgentTrigger,
    status: str,
    run_status: str | None = None,
    **conversation_kwargs,
) -> AgentMessage:
    """
    A reply with the given status, in a new conversation of the trigger, written
    by a run with the given status, or by none.
    """

    conversation = data_fixture.create_shared_agent_conversation(
        agent=trigger.agent, trigger=trigger, **conversation_kwargs
    )
    reply = data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        content="",
        status=status,
    )
    if run_status is not None:
        ChatRun.objects.create(
            run_type=AGENT_RUN_TYPE,
            chat_id=conversation.id,
            workspace=trigger.agent.workspace,
            status=run_status,
            context={"reply_id": reply.id},
        )
    return reply


@pytest.mark.django_db
@pytest.mark.parametrize(
    "going_status,run_status", [("running", "running"), ("waiting", None)]
)
def test_queued_and_going_replies_are_told_apart(
    data_fixture, going_status, run_status
):
    trigger = data_fixture.create_agent_trigger()
    other = data_fixture.create_agent_trigger(agent=trigger.agent)
    for status in ("completed", "failed", "cancelled"):
        trigger_reply(data_fixture, trigger, status)
    # Its run ended without saving it, as when persisting the outcome failed.
    trigger_reply(data_fixture, trigger, "running", run_status="failed")
    trigger_reply(data_fixture, other, going_status, run_status=run_status)
    first = trigger_reply(data_fixture, trigger, "queued")
    second = trigger_reply(data_fixture, trigger, "queued")
    trigger_reply(data_fixture, trigger, "queued", trashed=True)
    handler = AgentTriggerHandler()

    assert handler.has_going_reply(trigger) is False
    assert handler.count_queued_replies(trigger) == 2
    assert list(handler.get_queued_replies(trigger)) == [first, second]

    trigger_reply(data_fixture, trigger, going_status, run_status=run_status)

    assert handler.has_going_reply(trigger) is True


@pytest.mark.django_db
def test_the_sweep_lists_only_idle_triggers_with_queued_replies(
    data_fixture, django_assert_num_queries
):
    idle = data_fixture.create_agent_trigger()
    busy, stuck, finished, trashed = (
        data_fixture.create_agent_trigger(agent=idle.agent, trashed=is_trashed)
        for is_trashed in (False, False, False, True)
    )
    for trigger in (idle, busy, stuck, trashed):
        trigger_reply(data_fixture, trigger, "queued")
    trigger_reply(data_fixture, busy, "running", run_status="queued")
    trigger_reply(data_fixture, stuck, "running", run_status="failed")
    trigger_reply(data_fixture, finished, "completed")

    with django_assert_num_queries(1):
        idle_triggers = list(
            AgentTriggerHandler().list_idle_triggers_with_queued_replies()
        )

    assert idle_triggers == [idle, stuck]


@pytest.mark.django_db
def test_recent_conversation_times_count_what_triggers_started(data_fixture):
    trigger = data_fixture.create_agent_trigger()
    agent = trigger.agent
    sibling = data_fixture.create_agent_trigger(agent=agent)
    stranger = data_fixture.create_agent_trigger()
    created = {}
    for name, owner, at, extra in [
        ("old", trigger, "2026-11-10 09:00", {}),
        ("own", trigger, "2026-11-10 09:40", {}),
        ("deleted", trigger, "2026-11-10 09:45", {"trashed": True}),
        ("sibling", sibling, "2026-11-10 09:50", {}),
        ("stranger", stranger, "2026-11-10 09:55", {}),
    ]:
        with freeze_time(at):
            created[name] = data_fixture.create_shared_agent_conversation(
                agent=owner.agent, trigger=owner, **extra
            ).created_on
    with freeze_time("2026-11-10 09:58"):
        data_fixture.create_agent_conversation(agent=agent)
    since = datetime(2026, 11, 10, 9, 30, tzinfo=timezone.utc)
    handler = AgentTriggerHandler()

    assert sorted(handler.recent_conversation_times(trigger, since)) == [
        created["own"],
        created["deleted"],
    ]
    assert sorted(handler.recent_agent_conversation_times(agent, since)) == [
        created["own"],
        created["deleted"],
        created["sibling"],
    ]


@pytest.mark.django_db
def test_a_skip_and_a_firing_are_recorded_without_touching_updated_on(
    data_fixture,
):
    trigger = data_fixture.create_agent_trigger()
    updated_on = trigger.updated_on
    skipped_at = datetime(2026, 11, 10, 10, 42, tzinfo=timezone.utc)
    fired_at = skipped_at + timedelta(minutes=1)
    handler = AgentTriggerHandler()

    handler.record_skip(trigger, AgentTrigger.SkipReason.QUEUE_FULL, skipped_at)
    handler.record_fired(trigger, fired_at)

    trigger.refresh_from_db()
    assert (
        trigger.last_skipped_on,
        trigger.last_skipped_reason,
        trigger.last_fired_on,
        trigger.updated_on,
    ) == (skipped_at, "queue_full", fired_at, updated_on)


@pytest.mark.django_db
def test_a_trigger_conversation_can_be_queued_without_a_run(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)

    reply = queued_reply(trigger)

    message = reply.conversation.messages.get(role=AgentMessage.Role.TRIGGER)
    assert (message.content, reply.status, reply.content) == (
        "Check the inbox",
        "queued",
        "",
    )
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_the_oldest_queued_reply_starts_once_nothing_is_going(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)
    handler = AgentHandler()
    going = handler.start_trigger_conversation(trigger, "Still going").conversation
    first, second = queued_reply(trigger, "First"), queued_reply(trigger, "Second")

    assert handler.start_next_queued_reply(trigger) is None

    going.messages.filter(role=AgentMessage.Role.ASSISTANT).update(status="completed")
    started = handler.start_next_queued_reply(trigger)

    run = ChatRun.objects.get(chat_id=first.conversation_id)
    second.refresh_from_db()
    assert started == first
    assert (started.status, second.status) == ("running", "queued")
    assert (run.created_by, run.context) == (None, {"reply_id": first.id})
    assert handler.start_next_queued_reply(trigger) is None


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
def test_a_queued_reply_stays_queued_while_the_workspace_is_at_its_run_limit(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)
    hold_a_workspace_run(data_fixture, agent)
    reply = queued_reply(trigger)

    assert AgentHandler().start_next_queued_reply(trigger) is None

    queued = AgentMessage.objects.get(id=reply.id)
    assert (queued.status, queued.error_code, queued.updated_on) == (
        "queued",
        "",
        reply.updated_on,
    )
    assert ChatRun.objects.count() == 1
    lock = in_another_connection(
        lambda: AgentTrigger.objects.select_for_update(nowait=True).get(id=trigger.id)
    )
    assert lock.result(timeout=10) == trigger


def switch_off(user: AbstractUser, trigger: AgentTrigger) -> None:
    AgentTriggerHandler().update_trigger(trigger, enabled=False)


def delete_for_good(user: AbstractUser, trigger: AgentTrigger) -> None:
    AgentTriggerHandler().delete_trigger(user, trigger)
    TrashHandler.permanently_delete(trigger)


@pytest.mark.django_db
@pytest.mark.parametrize("stop", [switch_off, delete_for_good])
def test_switching_a_trigger_off_or_deleting_it_for_good_cancels_its_queued_replies(
    data_fixture, mocker, stop
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    trigger = data_fixture.create_agent_trigger(agent=agent)
    replies = [
        trigger_reply(data_fixture, trigger, status, trashed=trashed)
        for status, trashed in [("running", False), ("queued", False), ("queued", True)]
    ]
    activity = mocker.spy(agent_conversation_activity, "send")

    stop(user, trigger)

    assert [
        AgentMessage.objects.values_list("status", "error_code").get(id=reply.id)
        for reply in replies
    ] == [
        ("running", ""),
        ("cancelled", "not_started"),
        ("cancelled", "not_started"),
    ]
    activity.assert_called_once_with(
        mocker.ANY, conversation=replies[1].conversation, user=None
    )


def disable(user: AbstractUser, trigger: AgentTrigger) -> None:
    # Only switched-on triggers start, however the switch was turned off.
    AgentTrigger.objects.filter(id=trigger.id).update(enabled=False)


def trash_trigger(user: AbstractUser, trigger: AgentTrigger) -> None:
    TrashHandler.trash(user, trigger.agent.workspace, trigger.agent, trigger)


def trash_agent(user: AbstractUser, trigger: AgentTrigger) -> None:
    TrashHandler.trash(user, trigger.agent.workspace, trigger.agent, trigger.agent)


def trash_workspace(user: AbstractUser, trigger: AgentTrigger) -> None:
    workspace = trigger.agent.workspace
    TrashHandler.trash(user, workspace, None, workspace)


@pytest.mark.django_db
@pytest.mark.parametrize("stop", [disable, trash_trigger, trash_agent, trash_workspace])
def test_a_stopped_trigger_keeps_its_queued_replies_waiting(
    data_fixture, configured_agent, stop
):
    user = data_fixture.create_user()
    trigger = data_fixture.create_agent_trigger(agent=configured_agent(user=user))
    reply = queued_reply(trigger)

    stop(user, trigger)

    assert list(AgentTriggerHandler().list_idle_triggers_with_queued_replies()) == []
    assert AgentHandler().start_next_queued_reply(trigger) is None
    assert AgentMessage.objects.get(id=reply.id).status == "queued"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "trash,trash_item_type,trashed",
    [
        (trash_trigger, "agent_trigger", lambda trigger: trigger),
        (trash_agent, "application", lambda trigger: trigger.agent),
        (trash_workspace, "workspace", lambda trigger: trigger.agent.workspace),
    ],
)
def test_a_queued_reply_starts_once_its_trashed_trigger_is_restored(
    data_fixture, configured_agent, trash, trash_item_type, trashed
):
    user = data_fixture.create_user()
    trigger = data_fixture.create_agent_trigger(agent=configured_agent(user=user))
    reply = queued_reply(trigger)
    trash(user, trigger)

    TrashHandler.restore_item(user, trash_item_type, trashed(trigger).id)
    start_queued_trigger_replies()

    assert AgentMessage.objects.get(id=reply.id).status == "running"


def lock_the_trigger(trigger: AgentTrigger) -> None:
    AgentTrigger.objects.select_for_update().get(id=trigger.id)


def insert_a_conversation(trigger: AgentTrigger) -> None:
    AgentConversation.objects.create(
        uuid=uuid4(), agent=trigger.agent, trigger=trigger, title="Firing"
    )
    # The deferred foreign key check, run at commit, locks the trigger for key share.
    connection.check_constraints()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "hold,blocks", [(lock_the_trigger, True), (insert_a_conversation, False)]
)
def test_only_a_trigger_locked_by_another_caller_holds_its_queue_back(
    data_fixture, configured_agent, mocker, hold, blocks
):
    mocker.patch.object(ChatRunHandler, "_enqueue")
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)
    reply = queued_reply(trigger)

    def start_next() -> AgentMessage | None:
        return AgentHandler().start_next_queued_reply(trigger)

    with transaction.atomic():
        hold(trigger)
        started_while_held = in_another_connection(start_next).result(timeout=10)
    started_after = start_next()

    assert (started_while_held, started_after) == (
        (None, reply) if blocks else (reply, None)
    )
    assert ChatRun.objects.get().context == {"reply_id": reply.id}


@pytest.mark.django_db(transaction=True)
def test_a_conversation_trashed_while_its_reply_starts_isnt_started(
    data_fixture, configured_agent, mocker
):
    mocker.patch.object(ChatRunHandler, "_enqueue")
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)
    reply = queued_reply(trigger)

    with transaction.atomic():
        AgentConversation.objects.filter(id=reply.conversation_id).update(trashed=True)
        starting = in_another_connection(
            lambda: AgentHandler().start_next_queued_reply(trigger)
        )
        wait_for_a_lock_waiter()

    assert starting.result(timeout=10) is None
    assert AgentMessage.objects.get(id=reply.id).status == "queued"
    assert not ChatRun.objects.exists()
