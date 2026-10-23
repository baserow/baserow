import asyncio
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS
from django.test import override_settings

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIResponsesModel

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.chat_run_type import AgentChatRunType
from baserow.contrib.agent.constants import INTERRUPTED_REPLY_NOTE
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentTurn,
)
from baserow.contrib.agent.operations import ReadAgentConversationsOperationType
from baserow.contrib.agent.replies import create_reply_model
from baserow.contrib.agent.types import AgentMessageCreated, AgentReplyRequest
from baserow.core.cache import local_cache
from baserow.core.chat_runs.journal import ChatRunJournal
from baserow.core.chat_runs.models import ChatRun
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.trash.handler import TrashHandler

from .utils import agent_url, new_conversation, run_reply


def start(
    user: AbstractUser, agent: AgentApplication, content: str = "Hi"
) -> AgentMessageCreated:
    return CreateAgentConversationActionType.do(
        user, agent.id, uuid4(), uuid4(), content
    )


def run_of(conversation: AgentConversation) -> ChatRun:
    return ChatRun.objects.get(run_type="agent", chat_id=conversation.id)


@pytest.fixture
def reply_run(data_fixture, configured_agent):
    user = data_fixture.create_user()
    return run_of(start(user, configured_agent(user=user)).conversation)


@pytest.mark.django_db
def test_a_message_is_answered_privately_and_saved_without_null_characters(
    reply_run, reply_model
):
    reply_model.custom_output_text = "Hello\x00 from the agent"
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    Agent.instrument_all(InstrumentationSettings(tracer_provider=tracer_provider))
    try:
        run_reply(reply_run)
    finally:
        Agent.instrument_all(False)

    turn = AgentTurn.objects.get()
    reply = turn.messages.get(role="assistant")
    assert (reply_run.created_by_id, reply_run.context) == (
        turn.conversation.owner_user_id,
        {"turn_id": turn.id},
    )
    assert reply.content == "Hello from the agent"
    assert (turn.status, turn.error_code) == ("completed", "")
    assert exporter.get_finished_spans() == ()


@pytest.mark.django_db
def test_the_model_gets_the_instructions_and_recent_history(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, instructions="Be brief.")
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    for status, reply in [
        ("completed", "First"),
        ("cancelled", "Half"),
        ("failed", None),
    ]:
        turn = AgentTurn.objects.create(conversation=conversation, status=status)
        data_fixture.create_agent_message(
            conversation=conversation, turn=turn, content="Q"
        )
        if reply:
            data_fixture.create_agent_message(
                conversation=conversation, turn=turn, role="assistant", content=reply
            )
    mocker.patch("baserow.contrib.agent.handler.HISTORY_MESSAGE_LIMIT", 4)
    seen = []

    async def stream(messages, info):
        seen.extend(messages)
        yield "ok"

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    CreateAgentMessageActionType.do(user, agent.id, conversation.uuid, uuid4(), "Now?")

    run_reply(run_of(conversation))

    assert [(type(m).__name__, m.parts[0].content) for m in seen] == [
        ("ModelRequest", "Q"),
        ("ModelResponse", f"Half\n\n{INTERRUPTED_REPLY_NOTE}"),
        ("ModelRequest", "Q"),
        ("ModelResponse", INTERRUPTED_REPLY_NOTE),
        ("ModelRequest", "Now?"),
    ]
    assert seen[-1].instructions == "Be brief."


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reason,status,error_code",
    [
        ("cancelled", "cancelled", ""),
        ("timeout", "failed", "timeout"),
        (None, "failed", "failed"),
    ],
)
def test_unfinished_replies_persist_partial_text_without_private_error_details(
    reply_run, mocker, logs, reason, status, error_code
):
    emit_text = ChatRunJournal.emit_text

    def emit_and_stop(journal, text):
        emit_text(journal, text)
        if reason:
            journal.request_stop(reason)

    mocker.patch.object(ChatRunJournal, "emit_text", emit_and_stop)

    async def stream(messages, info):
        yield "Hel"
        if reason is None:
            raise ModelHTTPError(429, "m", body="Private provider details")
        await asyncio.Event().wait()

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )

    run_reply(reply_run)

    turn = AgentTurn.objects.get()
    reply_run.refresh_from_db()
    assert (turn.status, turn.error_code) == (status, error_code)
    assert (reply_run.status, reply_run.error_code) == (status, error_code)
    assert turn.messages.get(role="assistant").content == "Hel"
    assert [log.record["message"] for log in logs] == (
        [f"Agent turn {turn.id} could not be answered (ModelHTTPError, status 429)"]
        if reason is None
        else []
    )


@pytest.mark.django_db
def test_the_reply_model_is_built_without_a_request(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent(user=data_fixture.create_user())
    send = mocker.patch("httpx2.AsyncClient.send")
    request = AgentReplyRequest(
        turn_id=1,
        workspace=agent.workspace,
        instructions="",
        provider_type="openai",
        model_identifier="test-model",
        prompt="Hi",
        history=[],
    )

    # The autouse fixture patches the name chat_run_type imported, not this one.
    model, _ = create_reply_model(request)

    assert (type(model), model.model_name) == (OpenAIResponsesModel, "test-model")
    send.assert_not_called()


@pytest.mark.django_db
def test_a_reply_to_a_deleted_conversation_fails_without_an_error_log(reply_run, logs):
    AgentConversation.objects.get(id=reply_run.chat_id).delete()

    run_reply(reply_run)

    reply_run.refresh_from_db()
    assert (reply_run.status, reply_run.error_code) == ("failed", "failed")
    assert logs == []


@pytest.mark.django_db
def test_lost_and_unstarted_runs_end_their_turn(reply_run):
    conversation = AgentConversation.objects.get(id=reply_run.chat_id)
    run_type = AgentChatRunType()
    lost = reply_run
    unstarted = run_of(start(conversation.owner_user, conversation.agent).conversation)
    lost.status, lost.error_code = "failed", "interrupted"
    unstarted.status, unstarted.error_code = "failed", "not_started"
    events = [
        {"kind": "text.delta", "data": {"segment": 0, "text": "Hel\x00"}},
        {"kind": "text.delta", "data": {"segment": 0, "text": "lo"}},
    ]

    run_type.on_run_lost(lost, events)
    run_type.on_run_not_started(unstarted)

    lost_turn = AgentTurn.objects.get(id=lost.context["turn_id"])
    assert (lost_turn.status, lost_turn.error_code) == ("failed", "interrupted")
    assert lost_turn.messages.get(role="assistant").content == "Hello"
    unstarted_turn = AgentTurn.objects.get(id=unstarted.context["turn_id"])
    assert (unstarted_turn.status, unstarted_turn.error_code) == (
        "failed",
        "not_started",
    )
    assert not unstarted_turn.messages.filter(role="assistant").exists()


@pytest.mark.django_db
def test_the_interruption_warning_only_ends_turns_still_running(reply_run):
    run_type = AgentChatRunType()

    run_type.ensure_interruption_warning(reply_run)
    run_type.ensure_interruption_warning(reply_run)

    turn = AgentTurn.objects.get()
    assert (turn.status, turn.error_code) == ("failed", "interrupted")
    turn.status, turn.error_code = "completed", ""
    turn.save()
    run_type.ensure_interruption_warning(reply_run)
    turn.refresh_from_db()
    assert turn.status == "completed"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,error_code",
    [("unconfigure", "not_ready"), ("leave", "not_allowed"), ("trash", "not_allowed")],
)
def test_a_reply_rechecks_the_configuration_and_access(reply_run, change, error_code):
    user = reply_run.created_by
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    if change == "unconfigure":
        agent.instructions = ""
        agent.save()
    elif change == "leave":
        WorkspaceUser.objects.filter(user=user).delete()
    else:
        TrashHandler.trash(user, agent.workspace, agent, agent)

    run_reply(reply_run)

    turn = AgentTurn.objects.get()
    assert (turn.status, turn.error_code) == ("failed", error_code)
    assert not turn.messages.filter(role="assistant").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,can_follow",
    [
        pytest.param("other_member", False, id="another-member"),
        pytest.param("leave", False, id="owner-removed-from-the-workspace"),
        pytest.param(
            "deny_reading",
            True,
            id="owner-without-read-permission-still-follows-by-membership-only",
        ),
        pytest.param("trash", False, id="trashed-agent"),
    ],
)
def test_only_the_owner_reads_follows_and_stops_a_reply(
    data_fixture, reply_run, mocker, change, can_follow
):
    owner = reply_run.created_by
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    run_type = AgentChatRunType()
    assert run_type.can_read(owner, reply_run) and run_type.can_cancel(owner, reply_run)
    assert run_type.can_follow_chat(owner, reply_run.chat_id)
    user = owner
    if change == "other_member":
        user = data_fixture.create_user(workspace=agent.workspace)
    elif change == "leave":
        WorkspaceUser.objects.filter(user=owner).delete()
    elif change == "deny_reading":
        mocker.patch.object(
            CoreHandler,
            "check_permissions",
            autospec=True,
            side_effect=lambda handler, actor, operation, **kwargs: (
                operation != ReadAgentConversationsOperationType.type
            ),
        )
    else:
        TrashHandler.trash(owner, agent.workspace, agent, agent)
    if user == owner:
        # Like a new request: membership is cached on the user and in the thread.
        local_cache.clear()
        user = type(owner).objects.get(id=owner.id)

    assert not run_type.can_read(user, reply_run)
    assert not run_type.can_cancel(user, reply_run)
    assert run_type.can_follow_chat(user, reply_run.chat_id) is can_follow


@pytest.mark.django_db
def test_messages_show_completed_and_running_turns(
    api_client, api_user, configured_agent
):
    agent = configured_agent(user=api_user)
    payload = new_conversation()
    api_client.post(agent_url(agent, "conversations"), payload)
    run_reply(ChatRun.objects.get())
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])
    sent = api_client.post(messages_url, {"uuid": str(uuid4()), "content": "More"})
    running = ChatRun.objects.get(status="queued")

    listed = api_client.get(messages_url).json()["results"]

    assert [(m["role"], m["turn"]["status"], m["turn"]["run_id"]) for m in listed] == [
        ("user", "completed", None),
        ("assistant", "completed", None),
        ("user", "running", str(running.id)),
    ]
    assert sent.json()["message"]["turn"]["run_id"] == str(running.id)


@pytest.mark.django_db
def test_the_refresh_after_a_reply_reads_the_messages_from_the_primary(
    api_client, api_user, configured_agent, mocker
):
    agent = configured_agent(user=api_user)
    payload = new_conversation()
    api_client.post(agent_url(agent, "conversations"), payload)
    set_db_alias = mocker.patch("baserow.api.mixins.set_db_alias")

    response = api_client.get(
        agent_url(agent, "messages", conversation_uuid=payload["uuid"]),
        HTTP_X_BASEROW_REALTIME_RECOVERY="true",
    )

    assert response.status_code == 200
    set_db_alias.assert_called_once_with(DEFAULT_DB_ALIAS)


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
def test_busy_conversations_and_workspaces_are_refused_with_their_errors(
    api_client, api_user, configured_agent
):
    agent = configured_agent(user=api_user)
    payload = new_conversation()
    api_client.post(agent_url(agent, "conversations"), payload)
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])

    busy_conversation = api_client.post(
        messages_url, {"uuid": str(uuid4()), "content": "More"}
    )
    busy_workspace = api_client.post(
        agent_url(agent, "conversations"), new_conversation()
    )

    assert (busy_conversation.status_code, busy_conversation.json()["error"]) == (
        409,
        "ERROR_CHAT_RUN_IN_PROGRESS",
    )
    assert (busy_workspace.status_code, busy_workspace.json()["error"]) == (
        429,
        "ERROR_AGENT_BUSY",
    )
    assert AgentConversation.objects.count() == AgentTurn.objects.count() == 1
    assert AgentTurn.objects.get().messages.count() == ChatRun.objects.count() == 1
