import asyncio
import json
import time
from functools import wraps
from unittest.mock import ANY, call
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import DatabaseError
from django.test import override_settings
from django.urls import reverse

import pytest
from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent, ConversationTypeAdapter
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIResponsesModel

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.chat_run_type import AgentChatRunType
from baserow.contrib.agent.constants import (
    ASK_FIRST_INSTRUCTIONS,
    DISALLOWED_TOOL_CALL_NOTE,
    INTERRUPTED_CHANGES_NOTE,
    INTERRUPTED_REPLY_NOTE,
    REJECTED_TOOL_CALL_NOTE,
    RUN_AS_LOST_TOOL_CALL_NOTE,
    TOOL_CHANGED_CALL_NOTE,
    TOOL_RETRIES,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyTranscript,
)
from baserow.contrib.agent.operations import ReadAgentConversationsOperationType
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import (
    AgentResponder,
    build_history,
    create_reply_model,
)
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.types import (
    AgentMessageCreated,
    AgentReplyRequest,
    AgentReplyResult,
)
from baserow.contrib.database.models import Database
from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.mcp.handler import MCPServerHandler, MCPToolSettings
from baserow.core.action.registries import action_type_registry
from baserow.core.agents.service import AgentService as IdentityService
from baserow.core.chat_runs.constants import ChatRunStopReason
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.journal import ChatRunJournal
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.steps import ChatRunSteps
from baserow.core.exceptions import PermissionDenied
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent as Identity
from baserow.core.models import WorkspaceUser
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.signals import application_pending_count_updated
from baserow.core.tools.errors import ToolInputError
from baserow.core.trash.handler import TrashHandler

from ..integrations.mcp.utils import serve
from .utils import agent_url, new_conversation, run_reply


def start(user: AbstractUser, agent: AgentApplication) -> AgentMessageCreated:
    return action_type_registry.get_by_type(CreateAgentConversationActionType).do(
        user, agent.id, uuid4(), uuid4(), "Hi"
    )


def run_of(conversation: AgentConversation) -> ChatRun:
    return ChatRun.objects.get(run_type="agent", chat_id=conversation.id)


def reply_state(reply_id: int) -> tuple[str, str, str]:
    reply = AgentMessage.objects.get(id=reply_id)
    return reply.status, reply.error_code, reply.content


def allow_tools(
    data_fixture,
    agent: AgentApplication,
    tools: tuple[str, ...] = ("create_rows",),
    ask_first: tuple[str, ...] = (),
    with_identity: bool = True,
) -> Table:
    """
    Allow the Agent to call tools, next to a new table of its workspace.

    :param agent: The Agent to configure.
    :param tools: The tools it may call.
    :param ask_first: Those of them that wait for the owner's approval.
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
        allowed_tools=list(tools),
        ask_first_tools=list(ask_first),
    )
    return table


def row_names(table: Table) -> list[str]:
    return [row.name for row in table.get_model(attribute_names=True).objects.all()]


def respond(
    mocker, *responses: tuple[str | dict[int, DeltaToolCall], ...]
) -> list[list[ModelMessage]]:
    """
    Have the model stream the chunks of each response in turn, across the runs of
    a reply, then text.

    :param responses: The chunks of each of the model's first responses.
    :return: The messages the model got for each response, filled as it answers.
    """

    received: list[list[ModelMessage]] = []

    async def stream(messages, info):
        received.append(messages)
        index = len(received) - 1
        for chunk in responses[index] if index < len(responses) else ["Done."]:
            yield chunk

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    return received


@pytest.mark.parametrize("response", ["empty", "thinking-only"])
@pytest.mark.parametrize(
    "provider,model_name,attempts",
    [
        ("openai", "gpt-5", 2),
        ("anthropic", "claude-sonnet-4-6", 2),
        ("groq", "qwen/qwen3-32b", 2),
        ("groq", "openai/gpt-oss-20b", 4),
        ("groq", "openai/gpt-oss-120b", 4),
    ],
)
def test_output_retry_budget_follows_provider_validator(
    mocker, provider, model_name, attempts, response
):
    calls = []

    async def stream(messages, info):
        calls.append(messages)
        if response == "thinking-only":
            yield {0: DeltaThinkingPart(content="Still thinking.")}
        else:
            yield ""

    request = AgentReplyRequest(
        reply_id=1,
        workspace=None,
        instructions="",
        provider_type=provider,
        model_identifier=model_name,
        prompt="Hi",
    )
    responder = AgentResponder(
        request, mocker.Mock(), FunctionModel(stream_function=stream), {}
    )

    with pytest.raises(
        UnexpectedModelBehavior, match="Exceeded maximum output retries"
    ):
        asyncio.run(responder._run_model(None))

    assert len(calls) == attempts


def tool_call(tool_name: str, call_id: str, **arguments: object) -> DeltaToolCall:
    return DeltaToolCall(
        name=tool_name, json_args=json.dumps(arguments), tool_call_id=call_id
    )


def add_row(table: Table, call_id: str = "call_write") -> DeltaToolCall:
    return tool_call("create_rows", call_id, table_id=table.id, rows=[{"Name": "Plan"}])


@pytest.fixture
def reply_run(data_fixture, configured_agent):
    user = data_fixture.create_user()
    return run_of(start(user, configured_agent(user=user)).conversation)


@pytest.mark.django_db
def test_failed_input_summary_keeps_the_call_without_logging_payloads(
    reply_run, data_fixture, reply_model, mocker, logs
):
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    allow_tools(data_fixture, agent)
    request = AgentService().prepare_reply(reply_run.context["reply_id"])
    responder = AgentResponder(request, mocker.Mock(), reply_model, {})
    mocker.patch.object(
        agent_tool_type_registry.get("create_rows"),
        "get_step_input",
        side_effect=ValueError("PRIVATE_INPUT_ERROR_CANARY"),
    )
    arguments = {"rows": [{"Name": "PRIVATE_INPUT_ARGUMENT_CANARY"}]}

    description = responder._describe_call("create_rows", arguments)

    assert description == {
        "changes_data": True,
        "input": {},
    }
    assert [log.record["message"] for log in logs] == [
        "Agent tool create_rows step input failed (ValueError)"
    ]
    output = "".join(str(entry) for entry in logs)
    assert "PRIVATE_INPUT_ERROR_CANARY" not in output
    assert "PRIVATE_INPUT_ARGUMENT_CANARY" not in output


@pytest.mark.django_db
def test_provider_output_validator_is_used_without_agent_provider_rules(
    data_fixture, configured_agent, mocker
):
    from pydantic_ai import ModelRetry

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    validated = []

    def validate(ctx, output):
        validated.append(output)
        if output == "Rejected text":
            raise ModelRetry("Please correct the answer.")
        return output

    provider = generative_ai_model_type_registry.get(agent.provider_type)
    get_validator = mocker.patch.object(
        provider, "get_output_validator", create=True, return_value=validate
    )
    received = respond(mocker, ("Rejected text",), ("Corrected answer",))

    created = start(user, agent)
    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "Corrected answer")
    assert validated == ["Rejected text", "Corrected answer"]
    assert len(received) == 2
    get_validator.assert_called_once_with(agent.model_identifier)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "output,saved",
    [
        ("Hello\x00 from the agent", ("completed", "", "Hello from the agent")),
        ("\n\n", ("failed", "failed", "")),
        ("\x00 \n\x00", ("failed", "failed", "")),
        ("Hello\ud800 from the agent", ("completed", "", "Hello from the agent")),
    ],
    ids=["null-characters", "blank", "blank-after-cleaning", "lone-surrogate"],
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
        output.replace("\x00", "").replace("\ud800", ""),
    ]
    assert transcript.usage["requests"] == 1
    assert exporter.get_finished_spans() == ()


@pytest.mark.django_db
def test_a_step_with_text_postgresql_cannot_store_is_sent_and_saved_clean(
    reply_run, mocker
):
    journal = mocker.Mock()
    steps = ChatRunSteps(journal, lambda tool, arguments: {"input": {}})
    steps.on_event(FunctionToolCallEvent(ToolCallPart("create_fields", {}, "one")))
    error = {"code": "conflict", "message": "'a\ud800b' exists.\x00"}
    content = {
        "changed": False,
        "error": error,
        "errors": [{"item": "a\ud800b", **error}],
    }
    steps.on_event(
        FunctionToolResultEvent(ToolReturnPart("create_fields", content, "one"))
    )
    reply_id = reply_run.context["reply_id"]

    AgentHandler().finish_reply(
        reply_id, "completed", "", AgentReplyResult(text="Done", steps=steps.finish())
    )

    (step,) = AgentMessage.objects.get(id=reply_id).steps
    assert step["error_message"] == "'ab' exists."
    assert step["item_errors"] == [
        {"item": "ab", "code": "conflict", "message": "'ab' exists."}
    ]
    assert journal.emit.call_args.args[1] == step


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
    step = {"id": "s", "input": {}, "facts": {}}
    steps = [
        {**step, "tool": "list_tables", "status": "done", "changes_data": False},
        {**step, "tool": "create_rows", "status": "stopped", "changes_data": True},
        {**step, "tool": "delete_rows", "status": "rejected", "changes_data": True},
        {
            **step,
            "tool": "update_rows",
            "status": "failed",
            "error_code": "not_run",
            "changes_data": True,
        },
        "malformed",
    ]
    for status, reply, reply_steps in [
        ("completed", "Old", None),
        ("completed", "First", steps),
        ("cancelled", "Half", None),
        ("failed", "", steps),
    ]:
        data_fixture.create_agent_message(conversation=conversation, content="Q")
        data_fixture.create_agent_message(
            conversation=conversation,
            role="assistant",
            content=reply,
            status=status,
            steps=reply_steps,
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
    action_type_registry.get_by_type(CreateAgentMessageActionType).do(
        user, agent.id, conversation.uuid, uuid4(), "Now?"
    )

    run_reply(run_of(conversation))

    assert [(type(m).__name__, m.parts[0].content) for m in seen] == [
        ("ModelRequest", "Q"),
        ("ModelResponse", "First"),
        ("ModelRequest", "Q"),
        ("ModelResponse", f"Half\n\n{INTERRUPTED_REPLY_NOTE}"),
        ("ModelRequest", "Q"),
        (
            "ModelResponse",
            f"{INTERRUPTED_REPLY_NOTE}\n"
            f"{INTERRUPTED_CHANGES_NOTE.format(changes='create_rows (stopped)')}",
        ),
        ("ModelRequest", "Now?"),
    ]
    assert seen[-1].instructions == "Be brief."


@pytest.mark.django_db
@pytest.mark.parametrize(
    "identity_state,unavailable",
    [
        ("unset", False),
        ("active", False),
        ("trashed", True),
        ("missing", True),
        ("other_workspace", True),
        ("unknown_type", True),
        ("user", True),
        ("type_only", True),
        ("id_only", True),
    ],
)
def test_the_model_knows_when_its_configured_workspace_identity_is_unavailable(
    data_fixture, configured_agent, mocker, identity_state, unavailable
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, instructions="Be brief.")
    identity = Identity.objects.create(
        workspace=agent.workspace, name="PRIVATE_IDENTITY_NAME"
    )
    if identity_state != "unset":
        agent.run_as_subject_type = "core.Agent"
        agent.run_as_subject_id = identity.id
        if identity_state == "trashed":
            IdentityService().delete_agent(user, identity)
        elif identity_state == "missing":
            identity.delete()
        elif identity_state == "other_workspace":
            identity.workspace = data_fixture.create_workspace()
            identity.save()
        elif identity_state == "unknown_type":
            agent.run_as_subject_type = "unknown.subject"
        elif identity_state == "user":
            agent.run_as_subject_type = "auth.User"
            agent.run_as_subject_id = user.id
        elif identity_state == "type_only":
            agent.run_as_subject_id = None
        elif identity_state == "id_only":
            agent.run_as_subject_type = None
        agent.save()
    seen = []

    async def stream(messages, info):
        seen.append(messages[-1].instructions)
        yield "ok"

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "ok")
    assert seen[-1].startswith("Be brief.")
    assert (
        "The identity configured for your workspace access is no longer available."
        in seen[-1]
    ) is unavailable
    assert "PRIVATE_IDENTITY_NAME" not in seen[-1]
    agent.refresh_from_db()
    assert agent.instructions == "Be brief."


@pytest.mark.django_db
def test_workspace_identity_context_is_refreshed_for_each_reply(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, instructions="Be brief.")
    identity = Identity.objects.create(workspace=agent.workspace, name="Writer")
    agent.run_as_subject_type = "core.Agent"
    agent.run_as_subject_id = identity.id
    agent.save()
    IdentityService().delete_agent(user, identity)
    seen = []

    async def stream(messages, info):
        seen.append(messages[-1].instructions)
        yield "ok"

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)
    run_reply(run_of(created.conversation))
    TrashHandler.restore_item(user, "agent", identity.id)
    next_reply = action_type_registry.get_by_type(CreateAgentMessageActionType).do(
        user, agent.id, created.conversation.uuid, uuid4(), "Try again"
    )

    run_reply(ChatRun.objects.get(id=next_reply.run_id))

    assert "workspace access is no longer available" in seen[0]
    assert seen[1] == "Be brief."


@pytest.mark.django_db
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize(
    "reason,status,error_code",
    [
        ("cancelled", "cancelled", ""),
        ("timeout", "failed", "timeout"),
        (None, "failed", "failed"),
    ],
)
def test_unfinished_replies_log_error_details_only_in_debug_mode(
    reply_run, data_fixture, mocker, logs, settings, debug, reason, status, error_code
):
    settings.DEBUG = debug
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    table = allow_tools(data_fixture, agent)
    emit_text = ChatRunJournal.emit_text

    def emit_and_stop(journal, text):
        emit_text(journal, text)
        if reason and text:
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
        ("done", {"count": 1})
    ]
    transcript = AgentReplyTranscript.objects.get(reply_id=reply_id)
    assert (
        transcript.provider_type,
        transcript.model_identifier,
        transcript.model_messages,
        transcript.usage,
    ) == ("openai", "test-model", None, None)
    if reason is None:
        assert len(logs) == 1
        message = logs[0].record["message"]
        assert f"Agent reply {reply_id} failed" in message
        assert f"run_id={reply_run.id}" in message
        assert "provider='openai', model='test-model'" in message
        assert "ModelHTTPError, status 429" in message
        assert ("Private provider details" in message) is debug
        assert "Private row value" not in str(logs[0])
        assert logs[0].record["exception"] is None
    else:
        assert logs == []


@pytest.mark.django_db
def test_empty_groq_stream_logs_the_original_error_in_debug_mode(
    reply_run, mocker, logs, settings
):
    import httpx
    from groq import AsyncGroq
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    settings.DEBUG = True
    model = GroqModel(
        "openai/gpt-oss-120b",
        provider=GroqProvider(
            groq_client=AsyncGroq(
                api_key="PRIVATE_KEY_CANARY",
                http_client=httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(
                            200,
                            headers={"content-type": "text/event-stream"},
                            content=b"data: [DONE]\n\n",
                        )
                    )
                ),
            )
        ),
    )
    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(model, {}),
    )

    run_reply(reply_run)

    assert reply_state(reply_run.context["reply_id"]) == ("failed", "failed", "")
    assert len(logs) == 1
    assert (
        "UnexpectedModelBehavior: Streamed response ended without content or tool calls"
        in logs[0].record["message"]
    )
    assert "PRIVATE_KEY_CANARY" not in str(logs[0])
    assert logs[0].record["exception"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider,model_name",
    [
        ("openai", "test-model"),
        ("openai", "openai/gpt-oss-120b"),
        ("groq", "qwen/qwen3-32b"),
        ("groq", "allam-2-7b"),
    ],
)
def test_other_models_can_answer_with_tool_json_without_correction(
    data_fixture, configured_agent, mocker, provider, model_name
):
    user = data_fixture.create_user()
    agent = configured_agent(
        user=user,
        provider_type=provider,
        model_identifier=model_name,
        available_model=(provider, model_name),
    )
    table = allow_tools(data_fixture, agent)
    printed_call = json.dumps(
        {
            "name": "create_rows",
            "arguments": {"table_id": table.id, "rows": [{"Name": "Example"}]},
        }
    )
    received = respond(mocker, (printed_call,))

    created = start(user, agent)
    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", printed_call)
    assert row_names(table) == []
    assert len(received) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "stray-quote"])
def test_printed_tool_json_is_corrected_without_repeating_a_completed_change(
    data_fixture, configured_agent, mocker, model_name, malformed
):
    user = data_fixture.create_user()
    agent = configured_agent(
        user=user,
        provider_type="groq",
        model_identifier=model_name,
        available_model=("groq", model_name),
    )
    table = allow_tools(data_fixture, agent)
    printed_call = json.dumps(
        {
            "name": "create_rows",
            "arguments": {"table_id": table.id, "rows": [{"Name": "Not executed"}]},
        }
    )
    if malformed:
        printed_call = printed_call[:-1] + '"' + printed_call[-1]
    received = respond(
        mocker,
        ({0: add_row(table)},),
        (printed_call,),
        ("Added the row.",),
    )

    created = start(user, agent)
    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "Added the row.")
    assert row_names(table) == ["Plan"]
    assert len(received) == 3
    reply = AgentMessage.objects.get(id=created.reply.id)
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("create_rows", "done")
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "stray-quote"])
def test_repeated_printed_tool_json_fails_without_saving_it_or_replaying_changes(
    data_fixture, configured_agent, mocker, model_name, malformed
):
    user = data_fixture.create_user()
    agent = configured_agent(
        user=user,
        provider_type="groq",
        model_identifier=model_name,
        available_model=("groq", model_name),
    )
    table = allow_tools(data_fixture, agent)
    printed_call = json.dumps(
        {
            "name": "create_rows",
            "arguments": {"table_id": table.id, "rows": [{"Name": "Not executed"}]},
        }
    )
    if malformed:
        printed_call = printed_call[:-1] + '"' + printed_call[-1]
    received = respond(
        mocker, ({0: add_row(table)},), *((printed_call,) for _ in range(5))
    )

    created = start(user, agent)
    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("failed", "failed", "")
    assert row_names(table) == ["Plan"]
    assert len(received) == 5  # The write, then four output attempts.
    reply = AgentMessage.objects.get(id=created.reply.id)
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("create_rows", "done")
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
@pytest.mark.parametrize("malformed", [False, True], ids=["valid", "stray-quote"])
def test_printed_table_call_after_invalid_input_still_requires_approval(
    data_fixture, configured_agent, mocker, model_name, malformed
):
    user = data_fixture.create_user()
    agent = configured_agent(
        user=user,
        provider_type="groq",
        model_identifier=model_name,
        available_model=("groq", model_name),
    )
    existing = allow_tools(
        data_fixture, agent, ("create_tables",), ask_first=("create_tables",)
    )
    invalid = {
        "database_id": existing.database_id,
        "tables": [
            {
                "name": "Tasks",
                "primary_field_name": "Name",
                "fields": [
                    {
                        "name": "Status",
                        "type": "single_select",
                        "settings": {"options": [{"name": "Todo", "color": "black"}]},
                    }
                ],
            }
        ],
    }
    corrected = {
        "database_id": existing.database_id,
        "tables": [
            {
                "name": "Tasks",
                "primary_field_name": "Name",
                "fields": [
                    {
                        "name": "Status",
                        "type": "single_select",
                        "options": [{"value": "Todo", "color": "blue"}],
                    }
                ],
            }
        ],
    }
    printed_call = json.dumps({"name": "create_tables", "arguments": corrected})
    if malformed:
        printed_call = printed_call[:-1] + '"' + printed_call[-1]
    received = respond(
        mocker,
        ({0: tool_call("create_tables", "bad_1", **invalid)},),
        ({0: tool_call("create_tables", "bad_2", **invalid)},),
        (printed_call,),
        ({0: tool_call("create_tables", "corrected", **corrected)},),
        ("Created Tasks.",),
    )

    reply = pause(user, agent)

    assert reply.status == "waiting"
    assert reply.content == ""
    assert not Table.objects.filter(database=existing.database, name="Tasks").exists()
    assert [(step["status"], step.get("error_code")) for step in reply.steps] == [
        ("failed", "invalid_input"),
        ("failed", "invalid_input"),
        ("waiting", None),
    ]
    assert reply.approvals.get(status="pending").tool_call_id == "corrected"

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert (reply.status, reply.content) == ("completed", "Created Tasks.")
    table = Table.objects.get(database=existing.database, name="Tasks")
    assert list(
        table.field_set.get(name="Status").select_options.values_list("value", "color")
    ) == [("Todo", "blue")]
    assert len(received) == 5


@pytest.mark.django_db
def test_a_stop_during_a_change_waits_for_it_and_saves_it_as_interrupted(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    emit = ChatRunJournal.emit

    def emit_and_stop(journal, kind, data=None, flush_now=False):
        emit(journal, kind, data, flush_now)
        if kind == "step" and data["status"] == "running":
            journal.request_stop("cancelled")

    mocker.patch.object(ChatRunJournal, "emit", emit_and_stop)

    async def stream(messages, info):
        arguments = {"table_id": table.id, "rows": [{"Name": "Plan"}]}
        yield {0: DeltaToolCall(name="create_rows", json_args=json.dumps(arguments))}

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("cancelled", "", "")
    steps = AgentMessage.objects.get(id=created.reply.id).steps
    assert [(s["status"], s["changes_data"]) for s in steps] == [("stopped", True)]
    rows = [row.name for row in table.get_model(attribute_names=True).objects.all()]
    assert rows == ["Plan"]


@pytest.mark.django_db
def test_the_reply_model_is_the_configured_one(reply_run):
    request = AgentService().prepare_reply(reply_run.context["reply_id"])

    # The autouse fixture patches the name chat_run_type imported, not this one.
    model, _ = create_reply_model(request)

    assert (type(model), model.model_name) == (OpenAIResponsesModel, "test-model")


@pytest.mark.django_db
@pytest.mark.parametrize("trash_only", [False, True])
def test_a_reply_to_a_deleted_conversation_fails_without_an_error_log(
    reply_run, logs, trash_only
):
    conversation = AgentConversation.objects.filter(id=reply_run.chat_id)
    # A trashed conversation whose run wasn't stopped mustn't be answered either.
    conversation.update(trashed=True) if trash_only else conversation.delete()

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
                "status": "running",
                "changes_data": True,
                "input": {"requested_count": 3},
                "facts": {},
            },
        },
    ]
    activity = mocker.spy(agent_conversation_activity, "send")

    saved = [run_type.on_run_lost(lost, events), run_type.on_run_not_started(unstarted)]

    assert reply_state(lost.context["reply_id"]) == ("failed", "interrupted", "Hello")
    assert reply_state(unstarted.context["reply_id"]) == ("failed", "not_started", "")
    assert [(m["id"], m["content"]) for m in saved] == [
        (lost.context["reply_id"], "Hello"),
        (unstarted.context["reply_id"], ""),
    ]
    assert activity.call_count == 2
    assert not AgentReplyTranscript.objects.exists()
    assert saved[0]["steps"] == [{**events[-1]["data"], "status": "stopped"}]
    assert saved[1]["steps"] is None


HELD_STEP = {
    "id": "step_1",
    "tool": "create_rows",
    "status": "waiting",
    "changes_data": True,
    "input": {},
    "facts": {},
}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "result,content,step_status,transcript",
    [
        pytest.param(
            AgentReplyResult(
                text="Done.",
                provider_type="openai",
                model_identifier="new-model",
                model_messages=[{"kind": "response"}],
                usage={"requests": 2},
                steps=[{**HELD_STEP, "status": "done"}],
            ),
            "Done.",
            "done",
            ("new-model", [{"kind": "request"}, {"kind": "response"}], {"requests": 2}),
            id="model-result",
        ),
        pytest.param(
            AgentReplyResult(
                text="",
                provider_type="openai",
                model_identifier="new-model",
                steps=[{**HELD_STEP, "status": "stopped"}],
            ),
            "I will add a row.",
            "stopped",
            ("old-model", [{"kind": "request"}], {"requests": 1}),
            id="no-model-result",
        ),
        pytest.param(
            None,
            "I will add a row.",
            "failed",
            ("old-model", [{"kind": "request"}], {"requests": 1}),
            id="not-started",
        ),
    ],
)
def test_a_later_segment_of_a_reply_keeps_what_the_paused_one_saved(
    data_fixture, result, content, step_status, transcript
):
    reply = data_fixture.create_agent_message(
        role="assistant",
        status="running",
        content="I will add a row.",
        steps=[HELD_STEP],
    )
    data_fixture.create_agent_tool_approval(
        reply=reply, step_id=HELD_STEP["id"], status="approved"
    )
    AgentReplyTranscript.objects.create(
        reply=reply,
        provider_type="openai",
        model_identifier="old-model",
        model_messages=[{"kind": "request"}],
        usage={"requests": 1},
        paused_conversation={"messages": []},
    )

    AgentHandler().finish_reply(reply.id, "cancelled", "", result)

    reply.refresh_from_db()
    saved = reply.transcript
    assert (reply.content, [step["status"] for step in reply.steps]) == (
        content,
        [step_status],
    )
    assert (
        saved.model_identifier,
        saved.model_messages,
        saved.usage,
        saved.paused_conversation,
    ) == (*transcript, None)


@pytest.mark.django_db
@pytest.mark.parametrize("ended", ["completed", "waiting"])
def test_the_interruption_warning_only_ends_replies_still_running(
    reply_run, mocker, ended
):
    run_type = AgentChatRunType()
    reply_id = reply_run.context["reply_id"]
    activity = mocker.spy(agent_conversation_activity, "send")

    run_type.ensure_interruption_warning(reply_run)

    assert reply_state(reply_id) == ("failed", "interrupted", "")
    AgentMessage.objects.filter(id=reply_id).update(status=ended, error_code="")
    run_type.ensure_interruption_warning(reply_run)
    assert reply_state(reply_id) == (ended, "", "")
    activity.assert_called_once_with(
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
            "check_multiple_permissions",
            autospec=True,
            side_effect=lambda handler, checks, *args, **kwargs: {
                check: check.operation_name != ReadAgentConversationsOperationType.type
                for check in checks
            },
        )
    else:
        TrashHandler.trash(owner, agent.workspace, agent, agent)

    assert not run_type.can_read(user, reply_run)
    assert not run_type.can_cancel(user, reply_run)
    assert run_type.can_follow_chat(user, reply_run.chat_id) is can_follow


@pytest.mark.django_db
def test_a_shared_reply_is_followed_by_members_and_stopped_with_agent_update_access(
    data_fixture, configured_agent, mocker
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    outsider = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=admin, members=[member])
    )
    trigger = data_fixture.create_agent_trigger(agent=agent)
    conversation = (
        AgentHandler().start_trigger_conversation(trigger, "Tick").conversation
    )
    run = run_of(conversation)
    run_type = AgentChatRunType()
    check = mocker.spy(CoreHandler, "check_multiple_permissions")

    assert run.created_by is None
    assert run_type.can_read(member, run)
    assert run_type.can_follow_chat(member, conversation.id)
    assert run_type.can_cancel(member, run)
    assert [permission.operation_name for permission in check.call_args.args[1]] == [
        ReadAgentConversationsOperationType.type,
        UpdateApplicationOperationType.type,
    ]
    assert not run_type.can_read(outsider, run)
    assert not run_type.can_cancel(outsider, run)
    assert not run_type.can_follow_chat(outsider, conversation.id)


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
def test_workspaces_have_no_reply_limit_by_default(
    api_client, api_user, configured_agent
):
    agent = configured_agent(user=api_user)
    for _ in range(11):
        response = api_client.post(
            agent_url(agent, "conversations"), new_conversation()
        )
        assert response.status_code == 200

    assert ChatRun.objects.filter(status="queued").count() == 11


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
    data_fixture, configured_agent, mocker, with_identity, valid_facts, api_client
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent, with_identity=with_identity)
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
                "status": "done",
                "changes_data": True,
                "input": {
                    "requested_count": 1,
                    "values": {"table": table.name, "rows": [{"Name": "Plan"}]},
                },
                "facts": {"count": 1} if valid_facts else {},
            }
        ]
        streamed = [
            call.args[2] for call in emitted.call_args_list if call.args[1] == "step"
        ]
        assert [step["status"] for step in streamed] == ["running", "running", "done"]
        assert streamed[1]["input"] == steps[0]["input"]
        assert streamed[-1] == steps[0]
        run = run_of(created.conversation)
        assert run.outcome["steps"] == steps
        assert AgentMessage.objects.get(id=created.reply.id).transcript.model_messages
        api_client.force_authenticate(user)
        response = api_client.get(
            agent_url(agent, "messages", conversation_uuid=created.conversation.uuid)
        )
        assert response.status_code == 200
        saved_reply = next(
            message
            for message in response.json()["results"]
            if message["role"] == "assistant"
        )
        assert saved_reply["steps"] == steps
    else:
        assert steps is None
    rows = row_names(table)
    if with_identity:
        assert (offered, rows) == ([["create_rows"], ["create_rows"]], ["Plan"])
    else:
        assert (offered, rows) == ([[]], [])


@pytest.mark.django_db
def test_text_before_a_tool_call_is_cleared_when_the_call_starts(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    emitted = mocker.spy(ChatRunJournal, "emit_text")

    async def stream(messages, info):
        if len(messages) == 1:
            yield "Let me add it."
            arguments = {"table_id": table.id, "rows": [{"Name": "Plan"}]}
            yield {
                1: DeltaToolCall(name="create_rows", json_args=json.dumps(arguments))
            }
        else:
            yield "Done."

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    texts = [call.args[1] for call in emitted.call_args_list]
    assert texts == ["Let me add it.", "", "Done."]
    assert reply_state(created.reply.id) == ("completed", "", "Done.")


@pytest.mark.django_db
def test_a_reply_recovers_from_invalid_tool_calls(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
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
    rows = row_names(table)
    assert rows == ["Plan"]
    *invalid_steps, step = AgentMessage.objects.get(id=created.reply.id).steps
    assert [(s["status"], s["error_code"]) for s in invalid_steps] == [
        ("failed", "invalid_input")
    ] * TOOL_RETRIES
    assert step["status"] == "done"
    assert step["input"] == {
        "requested_count": 1,
        "values": {"table": table.name, "rows": [{"Name": "Plan"}]},
    }
    assert "error_code" not in step


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["clear", "replace"])
def test_workspace_configuration_changes_apply_to_the_next_generation(
    data_fixture, configured_agent, mocker, change
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    original_identity_id = agent.run_as_subject_id
    replacement = Identity.objects.create(workspace=agent.workspace, name="Reader")
    offered = []
    rounds = 0

    async def stream(messages, info):
        nonlocal rounds
        rounds += 1
        offered.append([tool.name for tool in info.function_tools])
        if rounds == 2:
            await sync_to_async(AgentHandler().update_configuration)(
                agent,
                run_as_subject_type="core.Agent" if change == "replace" else None,
                run_as_subject_id=replacement.id if change == "replace" else None,
                allowed_tools=["list_views"] if change == "replace" else [],
            )
        if rounds in (1, 2):
            yield {
                0: DeltaToolCall(
                    name="create_rows",
                    json_args=json.dumps(
                        {"table_id": table.id, "rows": [{"Name": f"Row {rounds}"}]}
                    ),
                )
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
    assert offered == [["create_rows"]] * 3
    assert list(
        table.get_model(attribute_names=True).objects.values_list("name", flat=True)
    ) == ["Row 1", "Row 2"]
    original_identity = Identity.objects.get(id=original_identity_id)
    replacement.refresh_from_db()
    assert original_identity.last_active is not None
    assert replacement.last_active is None

    next_reply = action_type_registry.get_by_type(CreateAgentMessageActionType).do(
        user, agent.id, created.conversation.uuid, uuid4(), "Try again"
    )
    request = AgentHandler().get_reply_request(
        AgentHandler().get_reply(next_reply.reply.id)
    )
    assert request.allowed_tool_names == (["list_views"] if change == "replace" else [])
    assert (request.acting_subject.pk if request.acting_subject else None) == (
        replacement.id if change == "replace" else None
    )
    run_reply(ChatRun.objects.get(id=next_reply.run_id))
    assert offered[-1] == (["list_views"] if change == "replace" else [])


@pytest.mark.django_db
def test_calls_to_tools_the_reply_does_not_offer_have_no_step(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    allow_tools(data_fixture, agent)
    calls = iter(["delete_rows"])

    async def stream(messages, info):
        name = next(calls, None)
        if name is None:
            yield "Done."
        else:
            yield {0: DeltaToolCall(name=name, json_args="{}")}

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    assert AgentMessage.objects.get(id=created.reply.id).steps is None


@pytest.mark.django_db
def test_a_reply_cannot_keep_writing_after_its_identity_is_trashed(
    data_fixture, configured_agent, mocker, settings
):
    settings.BASEROW_USE_LOCAL_CACHE = True
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    identity = Identity.objects.get(id=agent.run_as_subject_id)
    rounds = 0

    async def stream(messages, info):
        nonlocal rounds
        rounds += 1
        if rounds == 2:
            await sync_to_async(IdentityService().delete_agent)(user, identity)
        if rounds in (1, 2):
            name = "Before revocation" if rounds == 1 else "After revocation"
            yield {
                0: DeltaToolCall(
                    name="create_rows",
                    json_args=json.dumps(
                        {"table_id": table.id, "rows": [{"Name": name}]}
                    ),
                )
            }
        else:
            yield "Done."

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    identity.refresh_from_db()
    assert identity.trashed
    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    assert list(
        table.get_model(attribute_names=True).objects.values_list("name", flat=True)
    ) == ["Before revocation"]


@pytest.mark.django_db
def test_a_failed_tool_call_and_its_retry_are_two_steps_in_the_api(
    data_fixture, configured_agent, mocker, api_client
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    targets = iter([0, table.id])

    async def stream(messages, info):
        target = next(targets, None)
        if target is None:
            yield "Done."
        else:
            yield {
                0: DeltaToolCall(
                    name="create_rows",
                    json_args=json.dumps(
                        {"table_id": target, "rows": [{"Name": "Plan"}]}
                    ),
                )
            }

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)
    run_reply(run_of(created.conversation))

    steps = AgentMessage.objects.get(id=created.reply.id).steps
    assert [(step["status"], step.get("error_code")) for step in steps] == [
        ("failed", "not_found"),
        ("done", None),
    ]
    api_client.force_authenticate(user)
    response = api_client.get(
        agent_url(agent, "messages", conversation_uuid=created.conversation.uuid)
    )
    assert response.status_code == 200
    saved_reply = next(
        message
        for message in response.json()["results"]
        if message["role"] == "assistant"
    )
    assert saved_reply["steps"] == steps


@pytest.mark.django_db
def test_a_failed_tool_call_shows_its_message_but_never_its_hint(
    data_fixture, configured_agent, mocker, api_client
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(data_fixture, agent)
    calls = iter([table.id])

    async def stream(messages, info):
        target = next(calls, None)
        if target is None:
            yield "Done."
        else:
            yield {
                0: DeltaToolCall(
                    name="create_rows",
                    json_args=json.dumps(
                        {"table_id": target, "rows": [{"Name": "Plan"}]}
                    ),
                )
            }

    mocker.patch(
        "baserow.contrib.database.tools.rows._validate_rows",
        side_effect=ToolInputError("The rows don't fit.", hint="HINT_CANARY"),
    )
    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    created = start(user, agent)
    run_reply(run_of(created.conversation))

    api_client.force_authenticate(user)
    response = api_client.get(
        agent_url(agent, "messages", conversation_uuid=created.conversation.uuid)
    )
    reply = next(m for m in response.json()["results"] if m["role"] == "assistant")
    (step,) = reply["steps"]
    assert (step["status"], step["error_code"], step["error_message"]) == (
        "failed",
        "invalid_input",
        "The rows don't fit.",
    )
    assert "HINT_CANARY" not in json.dumps(response.json())


@pytest.mark.django_db
def test_saved_steps_keep_why_they_failed(data_fixture, configured_agent, api_client):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    created = start(user, agent)
    step = {
        "id": "call_1",
        "tool": "create_tables",
        "status": "failed",
        "error_code": "conflict",
        "error_message": "Tasks exists.",
        "item_errors": [{"item": "Tasks", "code": "conflict", "message": "Exists."}],
        "changes_data": True,
        "input": {},
        "facts": {},
    }
    AgentMessage.objects.filter(id=created.reply.id).update(steps=[step])

    api_client.force_authenticate(user)
    response = api_client.get(
        agent_url(agent, "messages", conversation_uuid=created.conversation.uuid)
    )

    reply = next(m for m in response.json()["results"] if m["role"] == "assistant")
    assert reply["steps"] == [step]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_identifier,effort,sent_effort",
    [
        ("gpt-5.1", None, None),
        ("gpt-5.1", "off", "none"),
        ("gpt-5.1", "high", "high"),
        # GPT-5 Pro only accepts high.
        ("gpt-5-pro", "low", "high"),
        ("gpt-4.1", "high", None),
    ],
)
def test_reply_requests_carry_the_reasoning_effort(
    configured_agent, model_identifier, effort, sent_effort
):
    agent = configured_agent()
    request = AgentReplyRequest(
        reply_id=1,
        workspace=agent.workspace,
        instructions="",
        provider_type="openai",
        model_identifier=model_identifier,
        prompt="Hi",
        history=[],
        reasoning_effort=effort,
    )
    model, model_settings = create_reply_model(request)
    sent = {}

    class RequestSent(Exception):
        pass

    async def create(**kwargs):
        sent.update(kwargs)
        raise RequestSent()

    model.client.responses.create = create
    with pytest.raises(RequestSent):
        asyncio.run(
            model.request(
                [ModelRequest.user_text_prompt("Hi")],
                model_settings,
                model.customize_request_parameters(ModelRequestParameters()),
            )
        )

    reasoning = sent.get("reasoning")
    assert (
        reasoning.get("effort") if isinstance(reasoning, dict) else None
    ) == sent_effort


@pytest.fixture
def ask_first_agent(
    data_fixture, configured_agent
) -> tuple[AbstractUser, AgentApplication, Table]:
    """An Agent that reads freely and asks its owner before it creates rows."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(
        data_fixture, agent, ("list_tables", "create_rows"), ask_first=("create_rows",)
    )
    return user, agent, table


def pause(user: AbstractUser, agent: AgentApplication) -> AgentMessage:
    """Send a message and run its reply until it waits for the owner's approval."""

    created = start(user, agent)
    run_reply(run_of(created.conversation))
    return AgentMessage.objects.get(id=created.reply.id)


def decide(user: AbstractUser, reply: AgentMessage, **decision: object) -> ChatRun:
    """
    Decide the reply's pending held call as its owner.

    :param decision: Whether the call may run, and why not.
    :return: The run continuing the reply, not executed yet.
    """

    conversation = reply.conversation
    approval = reply.approvals.get(status="pending")
    result = AgentService().decide_approvals(
        user,
        conversation.agent_id,
        conversation.uuid,
        [{"id": approval.id, **decision}],
    )
    return ChatRun.objects.get(id=result.run_id)


@pytest.mark.django_db
def test_a_reply_runs_its_reads_and_waits_for_approval_of_an_ask_first_call(
    ask_first_agent, mocker, api_client
):
    user, agent, table = ask_first_agent
    respond(mocker, ({0: tool_call("list_tables", "call_read"), 1: add_row(table)},))
    pending_count_updated = mocker.spy(application_pending_count_updated, "send")

    reply = pause(user, agent)

    assert (reply.status, reply.error_code, reply.content) == ("waiting", "", "")
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("list_tables", "done"),
        ("create_rows", "waiting"),
    ]
    assert list(
        reply.approvals.values_list("tool_call_id", "step_id", "tool_name", "status")
    ) == [("call_write", reply.steps[1]["id"], "create_rows", "pending")]
    assert row_names(table) == []
    paused = ConversationTypeAdapter.validate_python(
        reply.transcript.paused_conversation
    )
    assert [call.tool_call_id for call in paused.deferred_tool_requests.approvals] == [
        "call_write"
    ]
    run = run_of(reply.conversation)
    assert run.status == "completed"
    api_client.force_authenticate(user)
    listed = api_client.get(
        agent_url(agent, "messages", conversation_uuid=reply.conversation.uuid)
    ).json()["results"]
    assert run.outcome == listed[-1]
    assert pending_count_updated.call_args_list == [
        call(ANY, application=agent, user_ids=[user.id])
    ]


@pytest.mark.django_db
def test_a_held_write_is_waiting_while_a_sibling_read_still_runs(
    ask_first_agent, mocker
):
    user, agent, table = ask_first_agent
    respond(mocker, ({0: add_row(table), 1: tool_call("list_tables", "call_read")},))
    emitted = mocker.spy(ChatRunJournal, "emit")
    tool_type = type(agent_tool_type_registry.get("list_tables"))
    original = tool_type.function
    during_read = []

    @wraps(original)
    def read(*args, **kwargs):
        steps = {
            entry.args[2]["id"]: entry.args[2]
            for entry in emitted.call_args_list
            if entry.args[1] == "step"
        }
        during_read.extend((step["tool"], step["status"]) for step in steps.values())
        return original(*args, **kwargs)

    mocker.patch.object(tool_type, "function", read)

    reply = pause(user, agent)

    assert during_read == [("create_rows", "waiting"), ("list_tables", "running")]
    assert [
        entry.args[2]["status"]
        for entry in emitted.call_args_list
        if entry.args[1] == "step" and entry.args[2]["tool"] == "create_rows"
    ] == ["waiting", "waiting"]
    assert reply.status == "waiting"
    assert row_names(table) == []


@pytest.mark.django_db
def test_a_held_call_fails_when_its_reply_stops_before_pausing(ask_first_agent, mocker):
    user, agent, table = ask_first_agent
    respond(mocker, ({0: add_row(table), 1: tool_call("list_tables", "call_read")},))
    emitted = mocker.spy(ChatRunJournal, "emit")
    tool_type = type(agent_tool_type_registry.get("list_tables"))
    original = tool_type.function

    @wraps(original)
    def read(*args, **kwargs):
        journal = emitted.call_args.args[0]
        journal._loop.call_soon_threadsafe(
            journal.request_stop, ChatRunStopReason.CANCELLED
        )
        while journal.stop_reason is None:
            time.sleep(0.01)
        return original(*args, **kwargs)

    mocker.patch.object(tool_type, "function", read)
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    reply = AgentMessage.objects.get(id=created.reply.id)
    assert reply.status == "cancelled"
    assert [
        (step["status"], step.get("error_code"))
        for step in reply.steps
        if step["tool"] == "create_rows"
    ] == [("failed", "not_run")]
    assert row_names(table) == []


@pytest.mark.django_db
def test_a_held_call_waits_with_its_named_request(ask_first_agent, mocker):
    user, agent, table = ask_first_agent
    respond(mocker, ({0: add_row(table)},))

    reply = pause(user, agent)

    [step] = reply.steps
    assert step["status"] == "waiting"
    assert step["input"] == {
        "requested_count": 1,
        "values": {"table": table.name, "rows": [{"Name": "Plan"}]},
    }


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", ["create_database", "update_database"])
@pytest.mark.parametrize("approved", [True, False])
def test_database_changes_wait_for_approval_before_persisting(
    data_fixture, configured_agent, mocker, tool_name, approved
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(
        data_fixture,
        agent,
        ("list_databases", tool_name),
        ask_first=(tool_name,),
    )
    database = table.database
    original_name = database.name
    databases = Database.objects.filter(workspace=agent.workspace)
    original_count = databases.count()
    arguments = {"name": "Projects"}
    preview = {"name": "Projects"}
    if tool_name == "update_database":
        arguments["database_id"] = database.id
        preview = {"database": original_name, "new_name": "Projects"}
    respond(
        mocker,
        (
            {
                0: tool_call("list_databases", "call_read"),
                1: tool_call(tool_name, "call_write", **arguments),
            },
        ),
    )

    reply = pause(user, agent)

    assert reply.status == "waiting"
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("list_databases", "done"),
        (tool_name, "waiting"),
    ]
    assert reply.steps[1]["input"] == {"values": preview}
    assert databases.count() == original_count
    database.refresh_from_db()
    assert database.name == original_name

    run_reply(decide(user, reply, approved=approved))

    reply.refresh_from_db()
    assert reply.status == "completed"
    assert reply.steps[1]["status"] == ("done" if approved else "rejected")
    database.refresh_from_db()
    if tool_name == "create_database":
        assert databases.count() == original_count + int(approved)
        assert databases.filter(name="Projects").exists() is approved
    else:
        assert database.name == ("Projects" if approved else original_name)
        assert databases.count() == original_count


@pytest.mark.django_db
def test_a_held_call_that_names_a_hidden_table_waits_with_its_ids(
    ask_first_agent, mocker, data_fixture
):
    user, agent, _ = ask_first_agent
    other = data_fixture.create_database_table()
    data_fixture.create_text_field(table=other, name="Name", primary=True)
    respond(mocker, ({0: add_row(other)},))

    reply = pause(user, agent)

    assert [(step["status"], step["input"]) for step in reply.steps] == [
        (
            "waiting",
            {
                "requested_count": 1,
                "values": {"table_id": other.id, "rows": [{"Name": "••••"}]},
            },
        )
    ]
    assert reply.approvals.exists()
    assert row_names(other) == []


@pytest.mark.django_db
def test_a_retry_after_a_pause_gets_its_own_card(ask_first_agent, mocker):
    user, agent, table = ask_first_agent
    # A provider may reuse the invalid attempt's call id for the corrected call.
    respond(
        mocker,
        (
            {
                0: tool_call(
                    "create_rows", "call_invalid", table_id=table.id, rows="invalid"
                ),
                1: add_row(table),
            },
        ),
        ({0: add_row(table, "call_invalid")},),
    )
    reply = pause(user, agent)
    failed_id, held_id = [step["id"] for step in reply.steps]

    run_reply(decide(user, reply, approved=True))
    reply.refresh_from_db()
    assert [(step["id"], step["status"]) for step in reply.steps[:2]] == [
        (failed_id, "failed"),
        (held_id, "done"),
    ]
    assert reply.steps[2]["status"] == "waiting"

    run_reply(decide(user, reply, approved=True))
    reply.refresh_from_db()
    assert [step["status"] for step in reply.steps] == ["failed", "done", "done"]
    assert row_names(table) == ["Plan", "Plan"]


@pytest.mark.django_db
def test_changes_after_a_held_call_wait_too_so_they_keep_the_model_order(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(
        data_fixture,
        agent,
        ("list_tables", "create_rows", "update_rows"),
        ask_first=("create_rows",),
    )
    row = table.get_model(attribute_names=True).objects.create(name="Old")
    respond(
        mocker,
        (
            {
                0: add_row(table, "call_create"),
                1: tool_call(
                    "update_rows",
                    "call_update",
                    table_id=table.id,
                    rows=[{"id": row.id, "Name": "Changed"}],
                ),
                2: tool_call("list_tables", "call_read"),
            },
        ),
    )

    reply = pause(user, agent)

    assert reply.status == "waiting"
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("create_rows", "waiting"),
        ("update_rows", "waiting"),
        ("list_tables", "done"),
    ]
    assert list(reply.approvals.values_list("tool_call_id", "step_id", "pause")) == [
        ("call_create", reply.steps[0]["id"], 1),
        ("call_update", reply.steps[1]["id"], 1),
    ]
    assert row_names(table) == ["Old"]


@pytest.mark.django_db
def test_an_ask_first_call_with_invalid_arguments_holds_no_later_change(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(
        data_fixture,
        agent,
        ("list_tables", "create_rows", "update_rows"),
        ask_first=("create_rows",),
    )
    row = table.get_model(attribute_names=True).objects.create(name="Old")
    respond(
        mocker,
        (
            {
                0: tool_call(
                    "create_rows", "call_invalid", table_id=table.id, rows="invalid"
                ),
                1: tool_call(
                    "update_rows",
                    "call_update",
                    table_id=table.id,
                    rows=[{"id": row.id, "Name": "Changed"}],
                ),
            },
        ),
    )
    created = start(user, agent)

    run_reply(run_of(created.conversation))

    reply = AgentMessage.objects.get(id=created.reply.id)
    assert reply.status == "completed"
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("create_rows", "failed"),
        ("update_rows", "done"),
    ]
    assert not reply.approvals.exists()
    assert row_names(table) == ["Changed"]


@pytest.mark.django_db
def test_an_approved_call_runs_as_the_identity_and_the_reply_continues(
    ask_first_agent, mocker
):
    user, agent, table = ask_first_agent
    received = respond(
        mocker, ({0: tool_call("list_tables", "call_read"), 1: add_row(table)},)
    )
    reply = pause(user, agent)
    acted = mocker.spy(CreateRowsActionType, "do")
    emitted = mocker.spy(ChatRunJournal, "emit")

    run_reply(decide(user, reply, approved=True))

    resumed = AgentMessage.objects.get(id=reply.id)
    assert (resumed.status, resumed.content) == ("completed", "Done.")
    assert row_names(table) == ["Plan"]
    assert acted.call_args.args[0] == Identity.objects.get(id=agent.run_as_subject_id)
    read_id, write_id = [step["id"] for step in reply.steps]
    assert [(step["id"], step["status"]) for step in resumed.steps] == [
        (read_id, "done"),
        (write_id, "done"),
    ]
    assert [
        (entry.args[2]["id"], entry.args[2]["status"])
        for entry in emitted.call_args_list
        if entry.args[1] == "step"
    ] == [
        (read_id, "done"),
        (write_id, "waiting"),
        (write_id, "running"),
        (write_id, "running"),
        (write_id, "done"),
    ]
    assert [
        part.content
        for message in received[-1]
        for part in message.parts
        if isinstance(part, UserPromptPart)
    ] == ["Hi"]
    transcript = resumed.transcript
    assert (transcript.usage["requests"], transcript.paused_conversation) == (2, None)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "decision,denial",
    [
        (
            {"reason": "Use the other table"},
            f"{REJECTED_TOOL_CALL_NOTE} Their reason: Use the other table",
        ),
        ({}, REJECTED_TOOL_CALL_NOTE),
    ],
    ids=["reason", "no-reason"],
)
def test_a_rejected_call_never_runs_and_the_model_learns_why(
    ask_first_agent, mocker, decision, denial
):
    user, agent, table = ask_first_agent
    received = respond(mocker, ({0: add_row(table)},))
    reply = pause(user, agent)

    run_reply(decide(user, reply, approved=False, **decision))

    reply.refresh_from_db()
    assert (reply.status, [step["status"] for step in reply.steps]) == (
        "completed",
        ["rejected"],
    )
    assert row_names(table) == []
    assert [
        (part.tool_call_id, part.outcome, part.content)
        for part in received[-1][-1].parts
    ] == [("call_write", "denied", denial)]
    assert ASK_FIRST_INSTRUCTIONS in received[-1][-1].instructions


@pytest.mark.django_db
def test_a_resumed_reply_explains_approvals_after_ask_first_is_turned_off(
    ask_first_agent, mocker
):
    user, agent, table = ask_first_agent
    received = respond(mocker, ({0: add_row(table)},))
    reply = pause(user, agent)
    AgentHandler().update_configuration(
        agent, allowed_tools=["list_tables", "create_rows"], ask_first_tools=[]
    )

    run_reply(decide(user, reply, approved=False))

    assert ASK_FIRST_INSTRUCTIONS in received[-1][-1].instructions


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change",
    [
        "disallow_the_tool",
        "clear_the_identity",
        "switch_the_identity",
        "trash_the_identity",
    ],
)
def test_an_approved_call_fails_when_the_agent_may_no_longer_make_it(
    ask_first_agent, mocker, change
):
    user, agent, table = ask_first_agent
    received = respond(mocker, ({0: add_row(table)},))
    reply = pause(user, agent)
    if change == "disallow_the_tool":
        AgentHandler().update_configuration(
            agent, allowed_tools=["list_tables"], ask_first_tools=[]
        )
    elif change == "clear_the_identity":
        AgentHandler().update_configuration(
            agent, run_as_subject_type=None, run_as_subject_id=None
        )
    elif change == "switch_the_identity":
        other = Identity.objects.create(workspace=agent.workspace, name="Admin")
        AgentHandler().update_configuration(
            agent, run_as_subject_type="core.Agent", run_as_subject_id=other.id
        )
    else:
        Identity.objects.filter(id=agent.run_as_subject_id).update(trashed=True)

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert [(step["status"], step.get("error_code")) for step in reply.steps] == [
        ("failed", "permission_denied")
    ]
    assert list(reply.approvals.values_list("status", flat=True)) == ["approved"]
    assert row_names(table) == []
    assert [part.content for part in received[-1][-1].parts] == [
        DISALLOWED_TOOL_CALL_NOTE
        if change == "disallow_the_tool"
        else RUN_AS_LOST_TOOL_CALL_NOTE
    ]


@pytest.mark.django_db
def test_a_continued_reply_waits_again_for_a_later_call_even_with_a_reused_id(
    ask_first_agent, mocker
):
    user, agent, table = ask_first_agent
    respond(mocker, ({0: add_row(table)},), ({0: add_row(table)},))
    reply = pause(user, agent)

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert (reply.status, [step["status"] for step in reply.steps]) == (
        "waiting",
        ["done", "waiting"],
    )
    assert list(
        reply.approvals.values_list("tool_call_id", "step_id", "status", "pause")
    ) == [
        ("call_write", reply.steps[0]["id"], "approved", 1),
        ("call_write", reply.steps[1]["id"], "pending", 2),
    ]

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert (reply.status, [step["status"] for step in reply.steps]) == (
        "completed",
        ["done", "done"],
    )
    assert row_names(table) == ["Plan", "Plan"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ending,approved,status,error_code,step,rows",
    [
        ("cancelled", True, "cancelled", "", ("failed", "not_run"), []),
        ("cancelled", False, "cancelled", "", ("rejected", None), []),
        ("not_ready", True, "failed", "not_ready", ("failed", "not_run"), []),
        ("lost", True, "failed", "interrupted", ("stopped", None), []),
        ("persist_failed", True, "failed", "interrupted", ("stopped", None), ["Plan"]),
    ],
    ids=["cancelled", "cancelled-rejected", "not-ready", "lost", "persist-failed"],
)
def test_a_continuation_ending_without_a_saved_answer_keeps_the_paused_reply(
    ask_first_agent, mocker, ending, approved, status, error_code, step, rows
):
    user, agent, table = ask_first_agent
    respond(mocker, ("I will add a row.", {0: add_row(table)}))
    reply = pause(user, agent)
    paused = AgentReplyTranscript.objects.get(reply=reply)
    run = decide(user, reply, approved=approved)

    if ending == "cancelled":
        ChatRunHandler().request_cancel(run.id)
    elif ending == "not_ready":
        agent.instructions = ""
        agent.save()
        run_reply(run)
    elif ending == "lost":
        run.status, run.error_code = "failed", "interrupted"
        AgentChatRunType().on_run_lost(run, [])
    else:
        mocker.patch.object(
            AgentChatRunType, "persist_outcome", side_effect=DatabaseError
        )
        run_reply(run)

    assert reply_state(reply.id) == (status, error_code, "")
    reply.refresh_from_db()
    assert [(s["status"], s.get("error_code")) for s in reply.steps] == [step]
    assert row_names(table) == rows
    transcript = AgentReplyTranscript.objects.get(reply=reply)
    assert (
        transcript.model_messages,
        transcript.usage,
        transcript.paused_conversation,
    ) == (paused.model_messages, paused.usage, None)


def mcp_ticket_server(ran: list) -> FastMCP:
    server = FastMCP("test")

    @server.tool()
    def close_ticket(ticket: str, api_key: str = "") -> str:
        """Close the ticket."""

        ran.append(ticket)
        return "Closed."

    return server


def agent_with_mcp_tool(data_fixture, agent, mocker, ran, ask_first=True):
    """
    Give the Agent a server whose ``close_ticket`` tool is on.

    :return: The server, and the tool's name for the model.
    """

    serve(mocker, mcp_ticket_server(ran))
    integration = data_fixture.create_mcp_server_integration(
        application=agent,
        auth_header_name="Authorization",
        auth_header_value="Bearer one",
    )
    MCPServerHandler().refresh_tools(integration)
    MCPServerHandler().update_tools(
        integration,
        [MCPToolSettings("close_ticket", enabled=True, ask_first=ask_first)],
    )
    return integration, f"mcp{integration.id}_close_ticket"


@pytest.mark.django_db
def test_an_ask_first_mcp_call_waits_with_its_arguments_and_runs_once_approved(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    ran = []
    _, close = agent_with_mcp_tool(data_fixture, agent, mocker, ran)
    received = respond(
        mocker, ({0: tool_call(close, "call_mcp", ticket="T-1", api_key="s3cret")},)
    )

    reply = pause(user, agent)

    assert ran == []
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        (close, "waiting")
    ]
    # The owner decides on the arguments, a credential masked.
    assert reply.steps[0]["input"] == {
        "server": "Docs",
        "tool": "close_ticket",
        "values": {"ticket": "T-1", "api_key": "••••"},
    }
    assert reply.approvals.get().tool_key
    assert ASK_FIRST_INSTRUCTIONS in received[0][-1].instructions

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert ran == ["T-1"]
    assert (reply.status, [step["status"] for step in reply.steps]) == (
        "completed",
        ["done"],
    )


@pytest.mark.django_db
def test_an_mcp_write_after_a_held_call_waits_for_the_decision_too(
    ask_first_agent, data_fixture, mocker
):
    user, agent, table = ask_first_agent
    ran = []
    _, close = agent_with_mcp_tool(data_fixture, agent, mocker, ran, ask_first=False)
    respond(
        mocker, ({0: add_row(table), 1: tool_call(close, "call_mcp", ticket="T-1")},)
    )

    reply = pause(user, agent)

    assert ran == []
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        ("create_rows", "waiting"),
        (close, "waiting"),
    ]


def _sign_in_again(integration):
    integration.auth_header_value = "Bearer two"
    integration.save(update_fields=["auth_header_value"])


def _review_a_new_definition(integration):
    integration.tools.filter(name="close_ticket").update(definition_hash="new")


def _move_the_server(integration):
    integration.url = "https://other.example.com/mcp"
    integration.save(update_fields=["url"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change", [_sign_in_again, _review_a_new_definition, _move_the_server]
)
def test_an_approved_mcp_call_does_not_run_when_its_server_account_or_tool_changed(
    data_fixture, configured_agent, mocker, change
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    ran = []
    integration, close = agent_with_mcp_tool(data_fixture, agent, mocker, ran)
    received = respond(mocker, ({0: tool_call(close, "call_mcp", ticket="T-1")},))
    reply = pause(user, agent)

    change(integration)
    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert ran == []
    assert [step["status"] for step in reply.steps] == ["failed"]
    assert [
        (part.tool_call_id, part.outcome, part.content)
        for part in received[-1][-1].parts
    ] == [("call_mcp", "denied", TOOL_CHANGED_CALL_NOTE)]


@pytest.mark.django_db
def test_an_approved_mcp_call_does_not_run_once_the_tool_is_turned_off(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    ran = []
    integration, close = agent_with_mcp_tool(data_fixture, agent, mocker, ran)
    received = respond(mocker, ({0: tool_call(close, "call_mcp", ticket="T-1")},))
    reply = pause(user, agent)

    MCPServerHandler().update_tools(
        integration, [MCPToolSettings("close_ticket", enabled=False)]
    )
    run_reply(decide(user, reply, approved=True))

    assert ran == []
    assert [
        (part.tool_call_id, part.outcome, part.content)
        for part in received[-1][-1].parts
    ] == [("call_mcp", "denied", DISALLOWED_TOOL_CALL_NOTE)]


def test_history_treats_a_trigger_message_like_a_prompt():
    messages = [
        AgentMessage(role="trigger", content="Tick"),
        AgentMessage(role="assistant", content="Done", status="completed"),
        AgentMessage(role="user", content="More?"),
    ]

    assert [
        (type(message).__name__, message.parts[0].content)
        for message in build_history(messages)
    ] == [
        ("ModelRequest", "Tick"),
        ("ModelResponse", "Done"),
        ("ModelRequest", "More?"),
    ]


@pytest.mark.django_db
def test_an_unattended_reply_waits_for_a_member_to_approve_an_ask_first_call(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    table = allow_tools(
        data_fixture, agent, ("list_tables", "create_rows"), ask_first=("create_rows",)
    )
    agent_with_mcp_tool(data_fixture, agent, mocker, [])
    trigger = data_fixture.create_agent_trigger(
        agent=agent,
        service=data_fixture.create_core_periodic_service(timezone="Europe/Rome"),
    )
    respond(mocker, ({0: add_row(table)},))
    requested = mocker.spy(AgentHandler, "get_reply_request")

    conversation = (
        AgentHandler().start_trigger_conversation(trigger, "Tick").conversation
    )
    run_reply(run_of(conversation))

    request = requested.spy_return
    assert (
        request.allowed_tool_names,
        request.ask_first_tool_names,
        len(request.mcp_servers),
        request.timezone,
        request.prompt,
    ) == (["list_tables", "create_rows"], ["create_rows"], 1, "Europe/Rome", "Tick")
    reply = AgentMessage.objects.get(conversation=conversation, role="assistant")
    assert reply_state(reply.id) == ("waiting", "", "")
    assert row_names(table) == []

    member = data_fixture.create_user(workspace=agent.workspace)
    run_reply(decide(member, reply, approved=True))

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert row_names(table) == ["Plan"]


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["disable", "trash", "delete"])
def test_an_unattended_reply_stops_once_its_trigger_is_gone(
    data_fixture, configured_agent, change
):
    agent = configured_agent()
    trigger = data_fixture.create_agent_trigger(agent=agent)
    conversation = (
        AgentHandler().start_trigger_conversation(trigger, "Tick").conversation
    )
    if change == "disable":
        trigger.enabled = False
        trigger.save(update_fields=["enabled"])
    elif change == "trash":
        trigger.trashed = True
        trigger.save(update_fields=["trashed"])
    else:
        trigger.delete()

    run_reply(run_of(conversation))

    reply = AgentMessage.objects.get(conversation=conversation, role="assistant")
    assert reply_state(reply.id) == ("failed", "trigger_off", "")
