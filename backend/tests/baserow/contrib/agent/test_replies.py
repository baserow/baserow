import asyncio
import json
from unittest.mock import ANY
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.test import override_settings
from django.urls import reverse

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIResponsesModel

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.chat_run_type import AgentChatRunType
from baserow.contrib.agent.constants import INTERRUPTED_REPLY_NOTE, TOOL_RETRIES
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyTranscript,
)
from baserow.contrib.agent.operations import ReadAgentConversationsOperationType
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import create_reply_model
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_conversation_updated
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.contrib.database.table.models import Table
from baserow.core.chat_runs.journal import ChatRunJournal
from baserow.core.chat_runs.models import ChatRun
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent as Identity
from baserow.core.models import WorkspaceUser
from baserow.core.trash.handler import TrashHandler

from .utils import agent_url, new_conversation, run_reply


def start(user: AbstractUser, agent: AgentApplication) -> AgentMessageCreated:
    return CreateAgentConversationActionType.do(user, agent.id, uuid4(), uuid4(), "Hi")


def run_of(conversation: AgentConversation) -> ChatRun:
    return ChatRun.objects.get(run_type="agent", chat_id=conversation.id)


def reply_state(reply_id: int) -> tuple[str, str, str]:
    reply = AgentMessage.objects.get(id=reply_id)
    return reply.status, reply.error_code, reply.content


def allow_create_rows(
    data_fixture, agent: AgentApplication, with_identity: bool = True
) -> Table:
    """
    Allow the Agent to create rows, in a new table of its workspace.

    :param agent: The Agent to configure.
    :param with_identity: Whether the Agent runs as an identity, without which it
        calls no tool.
    :return: The table, with a primary ``Name`` field.
    """

    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=agent.workspace)
    )
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    identity = Identity.objects.create(workspace=agent.workspace, name="Ops")
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="core.Agent" if with_identity else None,
        run_as_subject_id=identity.id if with_identity else None,
        allowed_tools=["create_rows"],
    )
    return table


@pytest.fixture
def reply_run(data_fixture, configured_agent):
    user = data_fixture.create_user()
    return run_of(start(user, configured_agent(user=user)).conversation)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "output,saved",
    [
        ("Hello\x00 from the agent", ("completed", "", "Hello from the agent")),
        ("\n\n", ("failed", "failed", "")),
        ("\x00 \n\x00", ("failed", "failed", "")),
    ],
    ids=["null-characters", "blank", "blank-after-cleaning"],
)
def test_a_message_is_answered_privately_and_saved_clean(
    reply_run, reply_model, output, saved
):
    """Kuma traces every pydantic-ai Agent with content; conversations are private."""

    reply_model.custom_output_text = output
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    Agent.instrument_all(InstrumentationSettings(tracer_provider=tracer_provider))
    try:
        run_reply(reply_run)
    finally:
        Agent.instrument_all(False)

    reply = AgentMessage.objects.get(role="assistant")
    assert reply_state(reply.id) == saved
    transcript = reply.transcript
    assert (transcript.provider_type, transcript.model_identifier) == (
        "openai",
        "test-model",
    )
    messages = ModelMessagesTypeAdapter.validate_python(transcript.model_messages)
    assert [message.parts[0].content for message in messages] == [
        "Hi",
        output.replace("\x00", ""),
    ]
    assert transcript.usage["requests"] == 1
    assert exporter.get_finished_spans() == ()


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["ends", "starts"])
def test_listed_replies_have_their_run_or_are_read_again(
    api_client, api_user, configured_agent, mocker, change
):
    """A reply can end, or another start, between reading the messages and runs."""

    agent = configured_agent(user=api_user)
    payload = new_conversation()
    api_client.post(agent_url(agent, "conversations"), payload)
    if change == "starts":
        run_reply(ChatRun.objects.get())
    read_runs = AgentHandler.get_active_reply_runs

    def read_runs_while_replies_change(handler, conversation):
        if change == "ends":
            run_reply(ChatRun.objects.get())
        runs = read_runs(handler, conversation)
        if change == "starts":
            AgentService().create_message(
                api_user, agent.id, conversation.uuid, uuid4(), "More"
            )
        return runs

    mocker.patch.object(
        AgentHandler, "get_active_reply_runs", read_runs_while_replies_change
    )
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])

    listed = api_client.get(messages_url).json()["results"]

    assert [(m["role"], m["status"], m["run_id"]) for m in listed] == [
        ("user", None, None),
        ("assistant", "completed", None),
    ]


@pytest.mark.django_db
def test_the_model_gets_the_instructions_and_recent_history(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, instructions="Be brief.")
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    for status, reply in [
        ("completed", "Old"),
        ("completed", "First"),
        ("cancelled", "Half"),
        ("failed", ""),
    ]:
        data_fixture.create_agent_message(conversation=conversation, content="Q")
        data_fixture.create_agent_message(
            conversation=conversation, role="assistant", content=reply, status=status
        )
    mocker.patch("baserow.contrib.agent.handler.HISTORY_MESSAGE_LIMIT", 6)
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
        ("ModelResponse", "First"),
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
    reply_run, data_fixture, mocker, logs, reason, status, error_code
):
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    table = allow_create_rows(data_fixture, agent)
    emit_text = ChatRunJournal.emit_text

    def emit_and_stop(journal, text):
        emit_text(journal, text)
        if reason:
            journal.request_stop(reason)

    mocker.patch.object(ChatRunJournal, "emit_text", emit_and_stop)

    async def stream(messages, info):
        if len(messages) == 1:
            yield {
                0: DeltaToolCall(
                    name="create_rows",
                    json_args=json.dumps(
                        {"table_id": table.id, "rows": [{"Name": "Private row value"}]}
                    ),
                )
            }
            return
        yield "Hel"
        if reason is None:
            raise ModelHTTPError(429, "m", body="Private provider details")
        await asyncio.Event().wait()

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )

    run_reply(reply_run)

    reply_id = reply_run.context["reply_id"]
    assert reply_state(reply_id) == (status, error_code, "Hel")
    steps = AgentMessage.objects.get(id=reply_id).steps
    assert [(step["status"], step["facts"]) for step in steps] == [
        ("done", {"table": table.name, "count": 1})
    ]
    assert "Private row value" not in json.dumps(steps)
    transcript = AgentReplyTranscript.objects.get(reply_id=reply_id)
    assert (
        transcript.provider_type,
        transcript.model_identifier,
        transcript.model_messages,
        transcript.usage,
    ) == ("openai", "test-model", None, None)
    assert [log.record["message"] for log in logs] == (
        [f"Agent reply {reply_id} could not be written (ModelHTTPError, status 429)"]
        if reason is None
        else []
    )


@pytest.mark.django_db
def test_the_reply_model_is_the_configured_one(reply_run):
    request = AgentService().prepare_reply(reply_run.context["reply_id"])

    # The autouse fixture patches the name chat_run_type imported, not this one.
    model, _ = create_reply_model(request)

    assert (type(model), model.model_name) == (OpenAIResponsesModel, "test-model")


@pytest.mark.django_db
def test_a_reply_to_a_deleted_conversation_fails_without_an_error_log(reply_run, logs):
    AgentConversation.objects.get(id=reply_run.chat_id).delete()

    run_reply(reply_run)

    reply_run.refresh_from_db()
    assert (reply_run.status, reply_run.error_code) == ("failed", "failed")
    assert logs == []


@pytest.mark.django_db
def test_lost_and_unstarted_runs_end_their_reply(reply_run, mocker):
    conversation = AgentConversation.objects.get(id=reply_run.chat_id)
    run_type = AgentChatRunType()
    lost = reply_run
    unstarted = run_of(start(conversation.owner_user, conversation.agent).conversation)
    lost.status, lost.error_code = "failed", "interrupted"
    unstarted.status, unstarted.error_code = "failed", "not_started"
    events = [
        {"kind": "text.delta", "data": {"segment": 0, "text": "Hel"}},
        {"kind": "text.delta", "data": {"segment": 0, "text": "lo"}},
        {
            "kind": "step",
            "data": {
                "id": "call_1",
                "tool": "create_rows",
                "presentation_type": "create_rows",
                "status": "running",
                "changes_data": True,
                "input": {"requested_count": 3},
                "facts": {},
            },
        },
    ]
    updated = mocker.spy(agent_conversation_updated, "send")

    saved = [run_type.on_run_lost(lost, events), run_type.on_run_not_started(unstarted)]

    assert reply_state(lost.context["reply_id"]) == ("failed", "interrupted", "Hello")
    assert reply_state(unstarted.context["reply_id"]) == ("failed", "not_started", "")
    assert [(m["id"], m["content"]) for m in saved] == [
        (lost.context["reply_id"], "Hello"),
        (unstarted.context["reply_id"], ""),
    ]
    assert updated.call_count == 2
    assert not AgentReplyTranscript.objects.exists()
    assert saved[0]["steps"] == [{**events[-1]["data"], "status": "stopped"}]
    assert saved[1]["steps"] is None


@pytest.mark.django_db
def test_the_interruption_warning_only_ends_replies_still_running(reply_run, mocker):
    run_type = AgentChatRunType()
    reply_id = reply_run.context["reply_id"]
    updated = mocker.spy(agent_conversation_updated, "send")

    run_type.ensure_interruption_warning(reply_run)

    assert reply_state(reply_id) == ("failed", "interrupted", "")
    AgentMessage.objects.filter(id=reply_id).update(status="completed", error_code="")
    run_type.ensure_interruption_warning(reply_run)
    assert reply_state(reply_id) == ("completed", "", "")
    updated.assert_called_once_with(
        run_type,
        conversation=AgentConversation.objects.get(id=reply_run.chat_id),
        user=None,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,error_code",
    [
        ("unconfigure", "not_ready"),
        ("leave", "not_allowed"),
        ("deny_sending", "not_allowed"),
        ("trash", "not_allowed"),
    ],
)
def test_a_reply_rechecks_the_configuration_and_access(
    reply_run, mocker, change, error_code
):
    user = reply_run.created_by
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    if change == "unconfigure":
        agent.instructions = ""
        agent.save()
    elif change == "leave":
        WorkspaceUser.objects.filter(user=user).delete()
    elif change == "deny_sending":
        mocker.patch.object(
            CoreHandler, "check_permissions", side_effect=PermissionDenied
        )
    else:
        TrashHandler.trash(user, agent.workspace, agent, agent)

    run_reply(reply_run)

    assert reply_state(reply_run.context["reply_id"]) == ("failed", error_code, "")


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

    assert not run_type.can_read(user, reply_run)
    assert not run_type.can_cancel(user, reply_run)
    assert run_type.can_follow_chat(user, reply_run.chat_id) is can_follow


@pytest.mark.django_db
def test_lists_show_completed_and_running_replies(
    api_client, api_user, configured_agent
):
    agent = configured_agent(user=api_user)
    payload = new_conversation()
    conversations_url = agent_url(agent, "conversations")
    api_client.post(conversations_url, payload)
    finished = ChatRun.objects.get()
    run_reply(finished)
    idle = api_client.get(conversations_url).json()["results"]
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])
    sent = api_client.post(messages_url, {"uuid": str(uuid4()), "content": "More"})
    running = ChatRun.objects.get(status="queued")

    listed = api_client.get(messages_url).json()["results"]
    replying = api_client.get(conversations_url).json()["results"]
    # Followers apply the reply from its run instead of reading the messages.
    outcome = api_client.get(reverse("api:chat_runs:detail", args=[finished.id]))

    assert [(m["role"], m["status"], m["run_id"]) for m in listed] == [
        ("user", None, None),
        ("assistant", "completed", None),
        ("user", None, None),
        ("assistant", "running", str(running.id)),
    ]
    assert sent.json()["reply"]["run_id"] == str(running.id)
    assert [c["run_id"] for c in idle + replying] == [None, str(running.id)]
    assert sent.json()["conversation"]["run_id"] == str(running.id)
    assert outcome.json()["message"] == listed[1]


@pytest.mark.django_db(transaction=True)
def test_a_send_names_its_run_even_when_the_reply_ended_before_the_response(
    api_client, api_user, configured_agent
):
    agent = configured_agent(user=api_user)

    response = api_client.post(agent_url(agent, "conversations"), new_conversation())

    run = ChatRun.objects.get()
    assert run.status == "completed"
    assert response.json()["reply"]["run_id"] == str(run.id)


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
    assert AgentConversation.objects.count() == ChatRun.objects.count() == 1
    assert AgentMessage.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "with_identity,valid_facts", [(True, True), (True, False), (False, True)]
)
def test_a_reply_calls_the_allowed_tools_as_the_agent_identity(
    data_fixture, configured_agent, mocker, with_identity, valid_facts
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_create_rows(data_fixture, agent, with_identity)
    offered = []
    emitted = mocker.spy(ChatRunJournal, "emit")
    if not valid_facts:
        mocker.patch.object(
            agent_tool_type_registry.get("create_rows"),
            "get_step_facts",
            return_value={"count": object()},
        )

    async def stream(messages, info):
        offered.append([tool.name for tool in info.function_tools])
        if info.function_tools and len(messages) == 1:
            arguments = {"table_id": table.id, "rows": [{"Name": "Plan"}]}
            yield {
                0: DeltaToolCall(name="create_rows", json_args=json.dumps(arguments))
            }
        else:
            yield "Done."

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    steps = AgentMessage.objects.get(id=created.reply.id).steps
    if with_identity:
        assert steps == [
            {
                "id": ANY,
                "tool": "create_rows",
                "presentation_type": "create_rows",
                "status": "done",
                "changes_data": True,
                "input": {"requested_count": 1},
                "facts": {"table": table.name, "count": 1} if valid_facts else {},
            }
        ]
        streamed = [
            call.args[2] for call in emitted.call_args_list if call.args[1] == "step"
        ]
        assert [step["status"] for step in streamed] == ["running", "done"]
        assert streamed[-1] == steps[0]
        run = run_of(created.conversation)
        assert run.outcome["steps"] == steps
        assert AgentMessage.objects.get(id=created.reply.id).transcript.model_messages
    else:
        assert steps is None
    rows = [row.name for row in table.get_model(attribute_names=True).objects.all()]
    if with_identity:
        assert (offered, rows) == ([["create_rows"], ["create_rows"]], ["Plan"])
    else:
        assert (offered, rows) == ([[]], [])


@pytest.mark.django_db
def test_a_reply_recovers_from_invalid_tool_calls(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_create_rows(data_fixture, agent)
    invalid = {"table_id": table.id, "rows": "Plan"}
    valid = {"table_id": table.id, "rows": [{"Name": "Plan"}]}
    calls = iter([invalid] * TOOL_RETRIES + [valid])

    async def stream(messages, info):
        arguments = next(calls, None)
        if arguments is None:
            yield "Done."
        else:
            yield {
                0: DeltaToolCall(name="create_rows", json_args=json.dumps(arguments))
            }

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    rows = [row.name for row in table.get_model(attribute_names=True).objects.all()]
    assert rows == ["Plan"]
    steps = AgentMessage.objects.get(id=created.reply.id).steps
    assert [step["status"] for step in steps] == ["failed"] * TOOL_RETRIES + ["done"]
    assert all(step["input"] == {} and step["facts"] == {} for step in steps[:-1])
