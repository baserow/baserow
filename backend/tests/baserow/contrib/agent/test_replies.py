import asyncio
import json
from unittest.mock import ANY
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.test import override_settings
from django.urls import reverse

import pytest
from asgiref.sync import sync_to_async
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIResponsesModel

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.chat_run_type import AgentChatRunType
from baserow.contrib.agent.constants import (
    INTERRUPTED_CHANGES_NOTE,
    INTERRUPTED_REPLY_NOTE,
    TOOL_RETRIES,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
)
from baserow.contrib.agent.operations import ReadAgentConversationsOperationType
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import AgentResponder, create_reply_model
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_conversation_updated
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.contrib.database.table.models import Table
from baserow.core.agents.service import AgentService as IdentityService
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
def test_failed_input_summary_keeps_the_call_without_logging_payloads(
    reply_run, data_fixture, reply_model, mocker, logs
):
    agent = AgentConversation.objects.get(id=reply_run.chat_id).agent
    allow_create_rows(data_fixture, agent)
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
    step = {"id": "s", "input": {}, "facts": {}}
    steps = [
        {**step, "tool": "list_tables", "status": "done", "changes_data": False},
        {**step, "tool": "create_rows", "status": "stopped", "changes_data": True},
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
    CreateAgentMessageActionType.do(user, agent.id, conversation.uuid, uuid4(), "Now?")

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
    next_reply = CreateAgentMessageActionType.do(
        user, agent.id, created.conversation.uuid, uuid4(), "Try again"
    )

    run_reply(ChatRun.objects.get(id=next_reply.run_id))

    assert "workspace access is no longer available" in seen[0]
    assert seen[1] == "Be brief."


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
        ("done", {"table": table.name, "count": 1})
    ]
    assert [log.record["message"] for log in logs] == (
        [f"Agent reply {reply_id} could not be written (ModelHTTPError, status 429)"]
        if reason is None
        else []
    )


@pytest.mark.django_db
def test_a_stop_during_a_change_waits_for_it_and_saves_it_as_interrupted(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_create_rows(data_fixture, agent)
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
    rows = [row.name for row in table.get_model(attribute_names=True).objects.all()]
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
    table = allow_create_rows(data_fixture, agent)
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
    [step] = AgentMessage.objects.get(id=created.reply.id).steps
    assert step["status"] == "done"
    assert step["input"] == {"requested_count": 1}
    assert "error_code" not in step


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["clear", "replace"])
def test_workspace_configuration_changes_apply_to_the_next_generation(
    data_fixture, configured_agent, mocker, change
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_create_rows(data_fixture, agent)
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

    next_reply = CreateAgentMessageActionType.do(
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
    allow_create_rows(data_fixture, agent)
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
    table = allow_create_rows(data_fixture, agent)
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
def test_failed_tool_calls_keep_their_category_in_the_api(
    data_fixture, configured_agent, mocker, api_client
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_create_rows(data_fixture, agent)
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
    assert [step["status"] for step in steps] == ["failed", "done"]
    assert steps[0]["error_code"] == "not_found"
    assert "error_code" not in steps[1]
    assert "Not found in this workspace." not in json.dumps(steps)
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
@pytest.mark.parametrize(
    "effort,thinking",
    [(None, None), ("off", False), ("low", "low"), ("high", "high")],
)
def test_reply_model_settings_carry_the_reasoning_effort(
    data_fixture, configured_agent, effort, thinking
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, reasoning_effort=effort)
    created = start(user, agent)

    request = AgentHandler().get_reply_request(created.reply)
    _, model_settings = create_reply_model(request)

    assert model_settings.get("thinking") == thinking
