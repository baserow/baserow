from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ApprovalRequired

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage
from baserow_enterprise.assistant.exceptions import (
    AssistantChatWaitingForApproval,
    AssistantToolApprovalNotPending,
)
from baserow_enterprise.assistant.handler import AssistantHandler
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
    AssistantChatPrediction,
    AssistantToolApproval,
)
from baserow_enterprise.assistant.tools.agent.tools import (
    AgentSetup,
    apply_agent_setup,
    get_agent,
)
from baserow_enterprise.assistant.types import UIContext

from .utils import make_test_ctx


def _ctx(user, workspace, approved_key=None):
    ctx = make_test_ctx(user, workspace)
    ctx.tool_call_approved = approved_key is not None
    ctx.tool_call_metadata = {"tool_key": approved_key} if approved_key else None
    return ctx


def _held(ctx, setup, agent_id=None):
    with pytest.raises(ApprovalRequired) as held:
        apply_agent_setup(ctx, AgentSetup(**setup), thought="t", agent_id=agent_id)
    return held.value.metadata


@pytest.mark.django_db
def test_a_read_only_agent_is_created_without_approval(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)

    result = apply_agent_setup(
        _ctx(user, workspace),
        AgentSetup(
            name="Digest",
            instructions="Summarize open tickets.",
            run_as_identity_id=identity.id,
            allowed_tools=["list_tables"],
            add_triggers=[{"type": "periodic"}],
        ),
        thought="t",
    )

    assert result["changed"] and result["created"]
    setup = result["setup"]
    assert setup["instructions"] == "Summarize open tickets."
    assert setup["allowed_tools"] == ["list_tables"]
    assert [(t["type"], t["enabled"]) for t in setup["triggers"]] == [
        ("periodic", False)
    ]


@pytest.mark.django_db
def test_granting_a_tool_that_changes_data_waits_for_approval(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    setup = {
        "name": "Triage",
        "run_as_identity_id": identity.id,
        "allowed_tools": ["list_tables", "create_tables"],
        "ask_first_tools": [],
    }

    metadata = _held(_ctx(user, workspace), setup)

    assert (
        "Let the Agent use create_tables without asking first"
        in (metadata["details"]["changes"])
    )
    assert not AgentApplication.objects.filter(workspace=workspace).exists()

    result = apply_agent_setup(
        _ctx(user, workspace, approved_key=metadata["tool_key"]),
        AgentSetup(**setup),
        thought="t",
    )
    assert result["setup"]["allowed_tools"] == ["list_tables", "create_tables"]
    assert result["setup"]["ask_first_tools"] == []


@pytest.mark.django_db
def test_turning_off_ask_first_alone_waits_for_approval_then_applies(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    created = {
        "name": "Triage",
        "run_as_identity_id": identity.id,
        "allowed_tools": ["list_tables", "create_tables"],
    }
    metadata = _held(_ctx(user, workspace), created)
    agent = apply_agent_setup(
        _ctx(user, workspace, approved_key=metadata["tool_key"]),
        AgentSetup(**created),
        thought="t",
    )["setup"]
    assert agent["ask_first_tools"] == ["create_tables"]

    change = {"ask_first_tools": []}
    metadata = _held(_ctx(user, workspace), change, agent_id=agent["agent_id"])
    assert metadata["details"]["changes"] == [
        "Let the Agent use create_tables without asking first"
    ]

    result = apply_agent_setup(
        _ctx(user, workspace, approved_key=metadata["tool_key"]),
        AgentSetup(**change),
        thought="t",
        agent_id=agent["agent_id"],
    )
    assert result["setup"]["allowed_tools"] == ["list_tables", "create_tables"]
    assert result["setup"]["ask_first_tools"] == []


@pytest.mark.django_db
def test_turning_on_a_row_trigger_names_only_a_table_of_the_workspace(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    leads = data_fixture.create_database_table(user=user, name="Leads")
    leads.database.workspace = workspace
    leads.database.save()
    elsewhere = data_fixture.create_database_table(name="Payroll")
    trigger = {"type": "local_baserow_rows_created", "enabled": True}

    metadata = _held(
        _ctx(user, workspace),
        {
            "name": "Triage",
            "run_as_identity_id": identity.id,
            "add_triggers": [
                {**trigger, "table_id": leads.id},
                {**trigger, "table_id": elsewhere.id},
            ],
        },
    )

    assert metadata["details"]["changes"] == [
        "Run the Agent by itself when rows are created in Leads",
        "Run the Agent by itself when rows are created",
    ]


@pytest.mark.django_db
def test_an_approval_doesnt_apply_once_the_agent_changed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = apply_agent_setup(
        _ctx(user, workspace),
        AgentSetup(name="Bot", instructions="v1", run_as_identity_id=identity.id),
        thought="t",
    )["setup"]
    change = {"allowed_tools": ["create_tables"], "ask_first_tools": []}
    metadata = _held(_ctx(user, workspace), change, agent_id=agent["agent_id"])

    apply_agent_setup(
        _ctx(user, workspace),
        AgentSetup(instructions="v2"),
        thought="t",
        agent_id=agent["agent_id"],
    )
    result = apply_agent_setup(
        _ctx(user, workspace, approved_key=metadata["tool_key"]),
        AgentSetup(**change),
        thought="t",
        agent_id=agent["agent_id"],
    )

    assert result["changed"] is False
    current = get_agent(_ctx(user, workspace), agent["agent_id"], thought="t")
    assert current["allowed_tools"] == []


@pytest.mark.django_db
def test_a_new_tool_that_changes_data_asks_first_by_default(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    setup = {
        "name": "Bot",
        "run_as_identity_id": identity.id,
        "allowed_tools": ["list_tables", "create_tables"],
    }

    metadata = _held(_ctx(user, workspace), setup)
    assert metadata["details"]["changes"][-1] == (
        "Let the Agent use create_tables, asking first"
    )
    result = apply_agent_setup(
        _ctx(user, workspace, approved_key=metadata["tool_key"]),
        AgentSetup(**setup),
        thought="t",
    )
    assert result["setup"]["ask_first_tools"] == ["create_tables"]


@pytest.mark.django_db
def test_a_test_conversation_asks_first_for_every_tool_that_changes_data(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(
        workspace=workspace, provider_type="openai", model_identifier="m"
    )
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        allowed_tools=["list_tables", "create_tables"],
        ask_first_tools=[],
    )
    requests = {}
    for is_test in (False, True):
        conversation = data_fixture.create_agent_conversation(
            user=user, agent=agent, is_test=is_test
        )
        data_fixture.create_agent_message(conversation=conversation, content="Hi")
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
        )
        requests[is_test] = AgentHandler().get_reply_request(reply)

    assert requests[False].ask_first_tool_names == []
    assert requests[True].ask_first_tool_names == ["create_tables"]


def _waiting_chat(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(user=user, workspace=workspace, title="c")
    human = chat.messages.create(role=AssistantChatMessage.Role.HUMAN, content="Do")
    ai = chat.messages.create(
        role=AssistantChatMessage.Role.AI,
        content="I need your approval",
        artifacts={
            "paused": {
                "messages": [],
                "mode": "agent",
                "tool_call_ids": ["call-0", "call-1"],
            }
        },
    )
    AssistantChatPrediction.objects.create(human_message=human, ai_response=ai)
    approvals = [
        AssistantToolApproval.objects.create(
            message=ai, tool_call_id=f"call-{i}", tool_name="apply_agent_setup"
        )
        for i in range(2)
    ]
    ui_context = UIContext.model_validate(
        {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "user": {"id": user.id, "name": user.first_name, "email": user.email},
        }
    )
    return user, workspace, chat, approvals, ui_context


@pytest.mark.django_db
def test_kuma_continues_only_once_every_held_call_is_decided(data_fixture, mocker):
    start = mocker.patch(
        "baserow_enterprise.assistant.handler.ChatRunHandler.start_run"
    )
    user, workspace, chat, (first, second), ui_context = _waiting_chat(data_fixture)
    handler = AssistantHandler()

    with pytest.raises(AssistantChatWaitingForApproval):
        handler.send_message(user, workspace, chat.uuid, "Hi", ui_context, "")

    run, _ = handler.decide_approvals(
        user, chat, [{"id": first.id, "approved": True}], ui_context, ""
    )
    assert run is None and not start.called

    with pytest.raises(AssistantToolApprovalNotPending):
        handler.decide_approvals(
            user,
            chat,
            [{"id": second.id, "approved": True}, {"id": second.id, "approved": False}],
            ui_context,
            "",
        )

    handler.decide_approvals(
        user,
        chat,
        [{"id": second.id, "approved": False, "reason": "Not that table"}],
        ui_context,
        "",
    )
    context = start.call_args.args[4]
    assert context["resume_message_id"] == first.message_id
    second.refresh_from_db()
    assert (second.status, second.reason) == ("rejected", "Not that table")

    with pytest.raises(AssistantToolApprovalNotPending):
        handler.decide_approvals(
            user, chat, [{"id": first.id, "approved": True}], ui_context, ""
        )
