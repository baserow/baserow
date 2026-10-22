import asyncio
from dataclasses import replace
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS
from django.test import override_settings

import pytest
from asgiref.sync import async_to_sync
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.models.test import TestModel

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
from baserow.contrib.agent.replies import AgentResponder, create_reply_model
from baserow.contrib.agent.types import AgentMessageCreated, AgentReplyRequest
from baserow.core.cache import local_cache
from baserow.core.chat_runs.exceptions import ChatRunAlreadyActive, ChatRunLimitReached
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


def reply_request() -> AgentReplyRequest:
    return AgentReplyRequest(
        turn_id=1,
        workspace=None,
        instructions="",
        provider_type="openai",
        model_identifier="m",
        prompt="Hi",
        history=[],
    )


class FakeJournal:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.stop_reason: str | None = None
        self._stopped = asyncio.Event()

    def emit_text(self, text: str, variant: str | None = None) -> None:
        self.texts.append(text)

    async def wait_for_stop(self) -> None:
        await self._stopped.wait()

    def stop(self, reason: str) -> None:
        self.stop_reason = reason
        self._stopped.set()


@pytest.mark.django_db
def test_a_message_is_answered_by_its_own_run(data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    result = start(user, agent)
    run = run_of(result.conversation)
    assert (run.created_by_id, run.context) == (
        user.id,
        {"turn_id": result.message.turn_id},
    )

    run_reply(run)

    turn = AgentTurn.objects.get()
    reply = turn.messages.get(role="assistant")
    assert reply.content == "Hello from the agent"
    assert (result.message.author_user_id, reply.author_user_id) == (user.id, None)
    assert (turn.status, turn.error_code) == ("completed", "")
    assert (turn.provider_type, turn.model_identifier) == ("openai", "test-model")
    assert turn.usage["requests"] == 1
    assert turn.model_messages[-1]["parts"][0]["content"] == "Hello from the agent"
    assert turn.finished_on is not None


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


@pytest.mark.parametrize(
    "reason,status,error_code,error_logs",
    [
        ("cancelled", "cancelled", "", []),
        ("timeout", "failed", "timeout", []),
        (
            None,
            "failed",
            "failed",
            ["ERROR Agent turn 1 could not be answered (ModelHTTPError, status 429)"],
        ),
    ],
)
def test_an_unfinished_reply_keeps_its_partial_text(
    reason, status, error_code, error_logs, logs
):
    journal = FakeJournal()

    async def stream(messages, info):
        yield "Hel"
        if reason is None:
            raise ModelHTTPError(429, "m", body="Private provider details")
        journal.stop(reason)
        await asyncio.Event().wait()

    responder = AgentResponder(
        reply_request(), journal, FunctionModel(stream_function=stream), {}
    )

    outcome = async_to_sync(responder.answer)()

    assert (outcome.status, outcome.error_code) == (status, error_code)
    assert (outcome.result.text, outcome.result.model_messages) == ("Hel", None)
    assert journal.texts == ["Hel"]
    assert [
        f"{log.record['level'].name} {log.record['message']}" for log in logs
    ] == error_logs


@pytest.mark.django_db
def test_the_reply_model_is_built_without_a_request(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent(user=data_fixture.create_user())
    send = mocker.patch("httpx2.AsyncClient.send")
    request = replace(
        reply_request(), workspace=agent.workspace, model_identifier="test-model"
    )

    # The autouse fixture patches the name chat_run_type imported, not this one.
    model, _ = create_reply_model(request)

    assert (type(model), model.model_name) == (OpenAIResponsesModel, "test-model")
    send.assert_not_called()


@pytest.mark.django_db
def test_a_reply_drops_the_null_characters_postgres_cannot_store(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)

    async def stream(messages, info):
        yield "Hel\x00lo"

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    run = run_of(start(user, agent).conversation)

    run_reply(run)

    turn = AgentTurn.objects.get()
    assert turn.messages.get(role="assistant").content == "Hello"
    assert turn.model_messages[-1]["parts"][0]["content"] == "Hello"


def test_a_reply_is_not_traced_by_the_global_agent_instrumentation():
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    Agent.instrument_all(InstrumentationSettings(tracer_provider=tracer_provider))
    responder = AgentResponder(reply_request(), FakeJournal(), TestModel(), {})

    try:
        outcome = async_to_sync(responder.answer)()
    finally:
        Agent.instrument_all(False)

    assert outcome.status == "completed"
    assert exporter.get_finished_spans() == ()


@pytest.mark.django_db
def test_a_reply_to_a_deleted_conversation_fails_without_an_error_log(
    data_fixture, configured_agent, logs
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = start(user, agent).conversation
    run = run_of(conversation)
    conversation.delete()

    run_reply(run)

    run.refresh_from_db()
    assert (run.status, run.error_code) == ("failed", "failed")
    assert logs == []


@pytest.mark.django_db
def test_lost_and_unstarted_runs_end_their_turn(data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    run_type = AgentChatRunType()
    lost = run_of(start(user, agent).conversation)
    unstarted = run_of(start(user, agent).conversation)
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
def test_the_interruption_warning_only_ends_turns_still_running(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    run = run_of(start(user, agent).conversation)
    run_type = AgentChatRunType()

    run_type.ensure_interruption_warning(run)
    run_type.ensure_interruption_warning(run)

    turn = AgentTurn.objects.get()
    assert (turn.status, turn.error_code) == ("failed", "interrupted")
    turn.status, turn.error_code = "completed", ""
    turn.save()
    run_type.ensure_interruption_warning(run)
    turn.refresh_from_db()
    assert turn.status == "completed"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,error_code",
    [("unconfigure", "not_ready"), ("leave", "not_allowed"), ("trash", "not_allowed")],
)
def test_a_reply_rechecks_the_configuration_and_access(
    data_fixture, configured_agent, change, error_code
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    run = run_of(start(user, agent).conversation)
    if change == "unconfigure":
        agent.instructions = ""
        agent.save()
    elif change == "leave":
        WorkspaceUser.objects.filter(user=user).delete()
    else:
        TrashHandler.trash(user, agent.workspace, agent, agent)

    run_reply(run)

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
    data_fixture, configured_agent, mocker, change, can_follow
):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    run = run_of(start(owner, agent).conversation)
    run_type = AgentChatRunType()
    assert run_type.can_read(owner, run) and run_type.can_cancel(owner, run)
    assert run_type.can_follow_chat(owner, run.chat_id)
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

    assert not run_type.can_read(user, run)
    assert not run_type.can_cancel(user, run)
    assert run_type.can_follow_chat(user, run.chat_id) is can_follow


@pytest.mark.django_db
def test_a_conversation_answers_one_message_at_a_time(data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = start(user, agent).conversation

    with pytest.raises(ChatRunAlreadyActive):
        CreateAgentMessageActionType.do(
            user, agent.id, conversation.uuid, uuid4(), "More"
        )

    assert conversation.messages.count() == 1


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
def test_a_full_workspace_refuses_new_replies_without_saving(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    start(user, agent)

    with pytest.raises(ChatRunLimitReached):
        start(user, agent)

    assert AgentConversation.objects.count() == 1


@pytest.mark.django_db
def test_messages_show_their_author_and_the_reply_in_progress(
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

    author = {"id": api_user.id, "name": api_user.first_name}
    assert [
        (m["role"], m["author"], m["turn"]["status"], m["turn"]["run_id"])
        for m in listed
    ] == [
        ("user", author, "completed", None),
        ("assistant", None, "completed", None),
        ("user", author, "running", str(running.id)),
    ]
    assert sent.json()["message"]["turn"]["run_id"] == str(running.id)
    retried = api_client.post(
        messages_url, {"uuid": sent.json()["message"]["uuid"], "content": "More"}
    )
    assert retried.json()["message"]["turn"]["run_id"] == str(running.id)


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
