from unittest.mock import Mock

from django.test import override_settings

import pytest

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.tasks import (
    setup_periodic_agent_trigger_tasks,
    start_queued_trigger_replies,
)
from baserow.contrib.agent.triggers.dispatcher import agent_trigger_dispatcher
from baserow.contrib.agent.triggers.tasks import hand_off_trigger_queue
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.telemetry.tasks import BaserowTelemetryTask

from ..utils import hold_a_workspace_run, queued_reply


def test_the_queued_reply_sweep_runs_every_minute():
    sender = Mock()

    setup_periodic_agent_trigger_tasks(sender)

    sender.add_periodic_task.assert_called_once_with(
        60, start_queued_trigger_replies.s()
    )


@pytest.mark.django_db
def test_the_sweep_starts_the_queued_reply_of_idle_triggers_only(
    data_fixture, configured_agent, django_assert_num_queries
):
    with django_assert_num_queries(1):
        start_queued_trigger_replies()
    agent = configured_agent(user=data_fixture.create_user())
    idle, busy = (
        data_fixture.create_agent_trigger(agent=agent, on_overlap="wait")
        for _ in range(2)
    )
    AgentHandler().start_trigger_conversation(busy, "Still going")
    idle_reply, busy_reply = queued_reply(idle), queued_reply(busy)

    start_queued_trigger_replies()

    idle_reply.refresh_from_db()
    busy_reply.refresh_from_db()
    assert (idle_reply.status, busy_reply.status) == ("running", "queued")
    assert ChatRun.objects.get(chat_id=idle_reply.conversation_id).context == {
        "reply_id": idle_reply.id
    }


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
def test_a_reply_handed_off_at_the_run_limit_stays_queued_until_the_sweep_has_room(
    data_fixture, configured_agent, django_capture_on_commit_callbacks
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent, on_overlap="wait")
    going = (
        AgentHandler().start_trigger_conversation(trigger, "Still going").conversation
    )
    reply = queued_reply(trigger)
    other_run = hold_a_workspace_run(data_fixture, agent)

    with django_capture_on_commit_callbacks(execute=True):
        ChatRunHandler().request_cancel(ChatRun.objects.get(chat_id=going.id).id)

    queued = AgentMessage.objects.get(id=reply.id)
    assert (queued.status, queued.error_code) == ("queued", "")
    assert not ChatRun.objects.filter(chat_id=reply.conversation_id).exists()

    ChatRun.objects.filter(id=other_run.id).update(status="completed")
    start_queued_trigger_replies()

    run = ChatRun.objects.get(chat_id=reply.conversation_id)
    assert AgentMessage.objects.get(id=reply.id).status == "running"
    assert run.context == {"reply_id": reply.id}


@pytest.mark.django_db
def test_the_sweep_goes_on_when_the_readers_of_a_started_reply_cant_be_told(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent(user=data_fixture.create_user())
    replies = [
        queued_reply(data_fixture.create_agent_trigger(agent=agent)) for _ in range(2)
    ]
    mocker.patch.object(agent_conversation_activity, "send", side_effect=RuntimeError)
    captured = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.exception_capturer"
    )

    start_queued_trigger_replies()

    assert [AgentMessage.objects.get(id=reply.id).status for reply in replies] == [
        "running",
        "running",
    ]
    assert captured.call_count == 2


def clear_the_model(agent: AgentApplication, settings) -> None:
    AgentApplication.objects.filter(id=agent.id).update(model_identifier="")


def switch_agents_off(agent: AgentApplication, settings) -> None:
    settings.FEATURE_FLAGS = []


@pytest.mark.django_db
@pytest.mark.parametrize("hold_back", [clear_the_model, switch_agents_off])
def test_a_trigger_that_cant_fire_keeps_its_queue_through_hand_offs_and_sweeps(
    data_fixture, configured_agent, settings, hold_back
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent)
    reply = queued_reply(trigger)
    hold_back(agent, settings)

    hand_off_trigger_queue(trigger.id)
    start_queued_trigger_replies()

    assert AgentMessage.objects.get(id=reply.id).status == "queued"
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_with_the_broker_down_a_hand_off_fails_one_reply_and_leaves_the_rest_queued(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = data_fixture.create_agent_trigger(agent=agent, on_overlap="wait")
    replies = [queued_reply(trigger) for _ in range(3)]
    mocker.patch.object(BaserowTelemetryTask, "apply_async", side_effect=OSError)

    with django_capture_on_commit_callbacks(execute=True):
        agent_trigger_dispatcher.start_queued_replies(trigger)

    assert [
        AgentMessage.objects.values_list("status", "error_code").get(id=reply.id)
        for reply in replies
    ] == [("failed", "not_started"), ("queued", ""), ("queued", "")]
