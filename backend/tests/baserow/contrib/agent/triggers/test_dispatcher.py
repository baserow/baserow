from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.db import connection
from django.test import TestCase, override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.actions import CreateAgentConversationActionType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentTrigger,
)
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.triggers.dispatcher import agent_trigger_dispatcher
from baserow.contrib.integrations.core.constants import PERIODIC_INTERVAL_MINUTE
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.contrib.integrations.tasks import call_periodic_services_that_are_due
from baserow.core.action.registries import action_type_registry
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.services.registries import (
    TriggerServiceTypeMixin,
    service_type_registry,
)

DUE_AT = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
TICK_AT = "2026-11-09 10:00:30"


@pytest.fixture(autouse=True)
def queued_runs_stay_queued(mocker) -> None:
    # Eager Celery would otherwise run each reply the triggers start.
    mocker.patch.object(ChatRunHandler, "_enqueue")


def periodic_trigger(data_fixture, agent: AgentApplication, **kwargs) -> AgentTrigger:
    """A minute trigger due at ``DUE_AT``, with a fixed-text message formula."""

    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_MINUTE, minute=1, next_run_at=DUE_AT
    )
    kwargs.setdefault("message", "'Check the inbox'")
    return data_fixture.create_agent_trigger(agent=agent, service=service, **kwargs)


def next_run_at(trigger: AgentTrigger) -> datetime:
    return CorePeriodicService.objects.get(id=trigger.service_id).next_run_at


def tick() -> None:
    """Run the beat task once, 30 seconds after ``DUE_AT``, and what it queues."""

    with TestCase.captureOnCommitCallbacks(execute=True), freeze_time(TICK_AT):
        call_periodic_services_that_are_due()


def fire(services: list, payload: dict, **kwargs) -> list:
    """Send an event to the dispatcher and run the starts it queues."""

    with TestCase.captureOnCommitCallbacks(execute=True):
        return agent_trigger_dispatcher.on_event(services, payload, **kwargs)


@pytest.mark.django_db
def test_a_trigger_conversation_is_shared_and_answered_by_a_system_run(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    trigger = periodic_trigger(data_fixture, agent)

    conversation = (
        AgentHandler()
        .start_trigger_conversation(trigger, "  Check\nthe inbox  ")
        .conversation
    )

    message, reply = AgentMessage.objects.order_by("id")
    run = ChatRun.objects.get()
    assert conversation == AgentConversation.objects.get()
    assert (conversation.owner_user_id, conversation.trigger_id) == (None, trigger.id)
    assert conversation.title == "Check the inbox"
    assert (message.role, message.content) == ("trigger", "  Check\nthe inbox  ")
    assert (reply.role, reply.status, reply.content) == ("assistant", "running", "")
    assert (run.chat_id, run.created_by, run.status, run.context) == (
        conversation.id,
        None,
        "queued",
        {"reply_id": reply.id},
    )


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
def test_a_trigger_conversation_records_the_run_limit_on_its_reply(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    action_type_registry.get_by_type(CreateAgentConversationActionType).do(
        user, agent.id, uuid4(), uuid4(), "Hi"
    )
    trigger = periodic_trigger(data_fixture, agent)

    conversation = (
        AgentHandler()
        .start_trigger_conversation(trigger, "Check the inbox")
        .conversation
    )

    reply = AgentMessage.objects.get(conversation=conversation, role="assistant")
    assert (reply.status, reply.error_code) == ("failed", "chat_run_limit_reached")
    assert AgentConversation.objects.count() == 2
    assert ChatRun.objects.count() == 1


def test_the_dispatcher_listens_to_every_trigger_service_type():
    trigger_types = [
        service_type
        for service_type in service_type_registry.get_all()
        if isinstance(service_type, TriggerServiceTypeMixin)
    ]

    assert trigger_types
    assert all(
        agent_trigger_dispatcher.on_event in service_type.listeners
        for service_type in trigger_types
    )


@pytest.mark.django_db
def test_a_due_trigger_starts_its_conversation_and_tells_the_readers(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    trigger = periodic_trigger(data_fixture, agent)
    activity = mocker.spy(agent_conversation_activity, "send")

    tick()

    conversation = AgentConversation.objects.get()
    run = ChatRun.objects.get()
    assert (conversation.trigger_id, conversation.title) == (
        trigger.id,
        "Check the inbox",
    )
    assert AgentMessage.objects.get(role="trigger").content == "Check the inbox"
    activity.assert_called_once_with(
        agent_trigger_dispatcher, conversation=conversation, user=None, run_id=run.id
    )
    assert next_run_at(trigger) == DUE_AT + timedelta(minutes=1)


@pytest.mark.django_db
def test_a_trigger_starts_its_conversation_only_after_the_event_commits(
    data_fixture, configured_agent
):
    trigger = periodic_trigger(data_fixture, configured_agent())

    with TestCase.captureOnCommitCallbacks() as queued, freeze_time(TICK_AT):
        call_periodic_services_that_are_due()

    assert not AgentConversation.objects.exists()
    assert next_run_at(trigger) == DUE_AT + timedelta(minutes=1)
    for callback in queued:
        callback()
    assert AgentConversation.objects.get().trigger_id == trigger.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "message",
    [
        "datetime_format(get('trigger.triggered_at'), 'YYYY', 'Mars/Olympus')",
        "get('trigger.triggered_at') / 2",
    ],
)
def test_a_message_failing_at_run_time_opens_with_the_payload_and_fails_its_reply(
    data_fixture, configured_agent, mocker, logs, message
):
    trigger = periodic_trigger(data_fixture, configured_agent(), message=message)
    captured = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.exception_capturer"
    )

    tick()

    opening = AgentMessage.objects.get(role="trigger")
    reply = AgentMessage.objects.get(role="assistant")
    assert opening.content.startswith("Trigger data:")
    assert (reply.status, reply.error_code) == ("failed", "trigger_message_failed")
    assert not ChatRun.objects.exists()
    captured.assert_not_called()
    [log] = logs
    assert log.record["message"].startswith(
        f"Agent trigger {trigger.id} message failed"
    )


@pytest.mark.django_db
def test_a_due_trigger_opens_with_the_time_it_fired_in_the_service_timezone(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = periodic_trigger(
        data_fixture,
        agent,
        message="concat('Periodic trigger fired at ', get('trigger.fired_at'))",
    )
    CorePeriodicService.objects.filter(id=trigger.service_id).update(
        timezone="Europe/Rome"
    )

    tick()

    assert (
        AgentMessage.objects.get(role="trigger").content
        == "Periodic trigger fired at 2026-11-09 11:00 (Europe/Rome)"
    )


@pytest.mark.django_db
def test_every_trigger_of_an_event_gets_the_time_the_dispatcher_handled_it(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    twice = periodic_trigger(
        data_fixture,
        agent,
        message="concat(get('trigger.fired_at'), ' | ', get('trigger.fired_at'))",
    )
    once = periodic_trigger(data_fixture, agent, message="get('trigger.fired_at')")
    services = [twice.service, once.service]

    # Every clock read moves a minute on, so a second read would show up.
    with freeze_time(TICK_AT, auto_tick_seconds=60):
        fire(services, {})

    contents = AgentMessage.objects.filter(role="trigger").values_list(
        "content", flat=True
    )
    assert len(contents) == 2
    assert len({part for content in contents for part in content.split(" | ")}) == 1


@pytest.mark.django_db
def test_an_agent_trigger_leaves_the_periodic_payload_and_schema_unchanged(
    data_fixture, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = periodic_trigger(data_fixture, agent, message="get('trigger.fired_at')")
    service_type = service_type_registry.get(CorePeriodicTriggerServiceType.type)
    received = []

    def other_listener(services, event_payload, **kwargs):
        received.extend(event_payload(service) for service in services)

    service_type.start_listening(other_listener)
    try:
        tick()
    finally:
        service_type.stop_listening(other_listener)

    assert AgentMessage.objects.filter(role="trigger").exists()
    assert [set(payload) for payload in received] == [{"triggered_at", "next_run_at"}]
    assert service_type.generate_schema(trigger.service.specific) == {
        "title": f"Periodic{trigger.service_id}Schema",
        "type": "object",
        "properties": {
            "triggered_at": {"type": "string", "title": "Previous scheduled run"},
            "next_run_at": {"type": "string", "title": "Next scheduled run"},
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reason", ["disabled", "agent_trashed", "not_ready", "flag_off", "unavailable"]
)
def test_a_skipped_trigger_starts_nothing_but_keeps_its_schedule(
    data_fixture, configured_agent, settings, mocker, reason
):
    user = data_fixture.create_user()
    agent = (
        data_fixture.create_agent_application(user=user)
        if reason == "not_ready"
        else configured_agent(user=user)
    )
    trigger = periodic_trigger(data_fixture, agent, enabled=reason != "disabled")
    if reason == "agent_trashed":
        AgentApplication.objects_and_trash.filter(id=agent.id).update(trashed=True)
    if reason == "flag_off":
        settings.FEATURE_FLAGS = []
    if reason == "unavailable":
        mocker.patch(
            "baserow.contrib.agent.triggers.handler.AGENT_TRIGGER_TYPES_ENABLED", ()
        )

    tick()

    assert not AgentConversation.objects.exists()
    assert not ChatRun.objects.exists()
    assert next_run_at(trigger) == DUE_AT + timedelta(minutes=1)


@pytest.mark.django_db
def test_a_trashed_agent_queues_nothing_but_keeps_its_schedule(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    trigger = periodic_trigger(data_fixture, agent)
    AgentApplication.objects_and_trash.filter(id=agent.id).update(trashed=True)
    queued = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.start_trigger_conversation.delay"
    )

    tick()

    queued.assert_not_called()
    assert next_run_at(trigger) == DUE_AT + timedelta(minutes=1)


@pytest.mark.django_db
def test_a_trigger_that_cannot_be_queued_does_not_stop_the_others(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    triggers = [periodic_trigger(data_fixture, agent) for _ in range(2)]
    queued = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.start_trigger_conversation.delay",
        side_effect=[ConnectionError("broker down"), None],
    )

    tick()

    assert [call.args[0] for call in queued.call_args_list] == [
        trigger.id for trigger in triggers
    ]


@pytest.mark.django_db
def test_a_failing_trigger_is_rolled_back_and_logged_while_the_others_start(
    data_fixture, configured_agent, mocker, logs
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    failing = periodic_trigger(data_fixture, agent)
    working = periodic_trigger(data_fixture, agent, message="'Second'")
    original = AgentHandler._start_reply_run

    def start_or_fail(handler, conversation, reply):
        if conversation.trigger_id == failing.id:
            raise RuntimeError("boom")
        return original(handler, conversation, reply)

    mocker.patch.object(AgentHandler, "_start_reply_run", start_or_fail)
    captured = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.exception_capturer"
    )

    tick()

    conversation = AgentConversation.objects.get()
    assert (conversation.trigger_id, conversation.title) == (working.id, "Second")
    assert AgentMessage.objects.count() == 2
    assert [log.record["message"] for log in logs] == [
        f"Could not start agent trigger {failing.id}."
    ]
    assert isinstance(captured.call_args.args[0], RuntimeError)
    assert next_run_at(failing) == next_run_at(working) == DUE_AT + timedelta(minutes=1)


@pytest.mark.django_db
def test_an_event_without_a_message_formula_opens_with_its_payload(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    trigger = periodic_trigger(data_fixture, agent, message="")
    payload = {"triggered_at": "2026-11-09T10:00:00+00:00", "next_run_at": None}

    histories = fire([trigger.service], payload, user=user, isolate_failures=False)

    message = AgentMessage.objects.get(role="trigger")
    assert histories == []
    assert message.content.startswith("Trigger data:")
    assert '"triggered_at": "2026-11-09T10:00:00+00:00"' in message.content
    assert (
        AgentConversation.objects.get().title == " ".join(message.content.split())[:250]
    )


@pytest.mark.django_db
def test_a_database_error_while_matching_leaves_the_transaction_usable(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent(user=data_fixture.create_user())
    trigger = periodic_trigger(data_fixture, agent)
    mocker.patch("baserow.contrib.agent.triggers.dispatcher.exception_capturer")

    def failing_payload(service):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_trigger_missing_table")

    histories = agent_trigger_dispatcher.on_event([trigger.service], failing_payload)

    assert histories == []
    assert AgentTrigger.objects.filter(id=trigger.id).exists()
