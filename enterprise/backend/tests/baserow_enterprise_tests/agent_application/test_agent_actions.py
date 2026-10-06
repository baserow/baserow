import uuid
from unittest.mock import patch

from django.test.utils import override_settings

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.agents.service import AgentService
from baserow.core.handler import CoreHandler
from baserow.core.services.models import Service
from baserow.core.skills.handler import WorkspaceSkillHandler
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.agent_application.actions import (
    CancelAgentChatRunActionType,
    CreateAgentChatChannelActionType,
    CreateAgentToolActionType,
    CreateAgentTriggerActionType,
    DecideAgentToolApprovalActionType,
    DeleteAgentChatActionType,
    DeleteAgentChatChannelActionType,
    DeleteAgentToolActionType,
    DeleteAgentTriggerActionType,
    UpdateAgentChatChannelActionType,
    UpdateAgentDefinitionActionType,
    UpdateAgentToolActionType,
    UpdateAgentTriggerActionType,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatChannel,
    AgentChatToolApproval,
    AgentTool,
    AgentTrigger,
)
from baserow_enterprise.audit_log.models import AuditLogEntry

BROADCAST = "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"


@pytest.fixture
def setup(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    return user, session_id, workspace, application, agent, table


def _scope(application):
    return [ApplicationActionScopeType.value(application.id)]


def _undo(user, session_id, application):
    return ActionHandler.undo(user, _scope(application), session_id)


def _redo(user, session_id, application):
    return ActionHandler.redo(user, _scope(application), session_id)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_tool_is_undoable(setup):
    user, session_id, workspace, application, agent, table = setup

    with patch(BROADCAST):
        tool = CreateAgentToolActionType.do(
            user, agent, "service", name="Mail", service_type_str="smtp_email"
        )
        service_id = tool.service_id

        _undo(user, session_id, application)
        assert not AgentTool.objects.filter(id=tool.id).exists()
        assert AgentTool.objects_and_trash.get(id=tool.id).trashed is True
        # The service survives in the trash so a redo brings the tool back whole.
        assert Service.objects.filter(id=service_id).exists()

        _redo(user, session_id, application)
    assert AgentTool.objects.get(id=tool.id).service_id == service_id


@pytest.mark.django_db
def test_update_tool_is_undoable_including_service_values(setup):
    user, session_id, workspace, application, agent, table = setup
    identity = AgentService().create_agent(user, workspace, name="Identity")
    with patch(BROADCAST):
        tool = CreateAgentToolActionType.do(
            user,
            agent,
            "service",
            name="Mail",
            service_type_str="smtp_email",
            service_values={"subject": "'Hello'"},
        )
        Action.objects.all().delete()

        UpdateAgentToolActionType.do(
            user,
            tool,
            name="Mail v2",
            config={"inputs": [{"name": "x", "type": "string"}]},
            service_values={"subject": "'Bye'"},
            identity_id=identity.id,
        )
        tool.refresh_from_db()
        assert tool.name == "Mail v2"
        assert tool.identity_id == identity.id
        assert tool.service.specific.subject["formula"] == "'Bye'"

        _undo(user, session_id, application)
        tool.refresh_from_db()
        assert tool.name == "Mail"
        assert tool.config == {}
        assert tool.identity_id is None
        assert tool.service.specific.subject["formula"] == "'Hello'"

        _redo(user, session_id, application)
        tool.refresh_from_db()
        assert tool.name == "Mail v2"
        assert tool.service.specific.subject["formula"] == "'Bye'"

        # Saving the same values again does not use up an undo step.
        Action.objects.all().delete()
        UpdateAgentToolActionType.do(user, tool, name="Mail v2")
    assert Action.objects.count() == 0


@pytest.mark.django_db
def test_delete_tool_is_undoable_and_permanent_delete_removes_service(setup):
    user, session_id, workspace, application, agent, table = setup
    with patch(BROADCAST):
        tool = CreateAgentToolActionType.do(
            user, agent, "service", service_type_str="smtp_email"
        )
        Action.objects.all().delete()

        DeleteAgentToolActionType.do(user, tool)
        assert not AgentTool.objects.filter(id=tool.id).exists()
        assert agent.tools.count() == 0

        _undo(user, session_id, application)
        assert AgentTool.objects.filter(id=tool.id).exists()

        _redo(user, session_id, application)
        assert not AgentTool.objects.filter(id=tool.id).exists()

        TrashHandler.permanently_delete(AgentTool.objects_and_trash.get(id=tool.id))
    assert not AgentTool.objects_and_trash.filter(id=tool.id).exists()
    assert not Service.objects.filter(id=tool.service_id).exists()


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_trigger_actions_are_undoable_and_a_trashed_trigger_is_inert(setup):
    user, session_id, workspace, application, agent, table = setup
    integration = application.integrations.first()
    with patch(BROADCAST):
        trigger = CreateAgentTriggerActionType.do(
            user,
            application,
            "local_baserow_rows_created",
            service_values={"table_id": table.id, "integration_id": integration.id},
        )
        Action.objects.all().delete()

        UpdateAgentTriggerActionType.do(user, trigger, enabled=False)
        trigger.refresh_from_db()
        assert trigger.enabled is False
        _undo(user, session_id, application)
        trigger.refresh_from_db()
        assert trigger.enabled is True
        _redo(user, session_id, application)
        trigger.refresh_from_db()
        assert trigger.enabled is False
        Action.objects.all().delete()

        DeleteAgentTriggerActionType.do(user, trigger)
        # Trigger dispatch and listings go through the default manager, so a
        # trashed trigger never fires.
        assert not AgentTrigger.objects.filter(id=trigger.id).exists()
        assert AgentTrigger.objects.filter(service_id=trigger.service_id).count() == 0
        _undo(user, session_id, application)
        assert AgentTrigger.objects.filter(id=trigger.id).exists()
        Action.objects.all().delete()

        # Undoing the creation trashes it again.
        _undo(user, session_id, application)  # nothing left to undo: no-op
        CreateAgentTriggerActionType.do(user, application, "periodic")
        _undo(user, session_id, application)
    assert AgentTrigger.objects.filter(application=application).count() == 1


# ---------------------------------------------------------------------------
# Chat channels
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_channel_actions_are_undoable_and_keep_secrets_out_of_the_history(setup):
    user, session_id, workspace, application, agent, table = setup
    with patch(BROADCAST):
        channel = CreateAgentChatChannelActionType.do(
            user,
            application,
            "slack",
            name="Support",
            config={"bot_token": "xoxb-secret", "signing_secret": "sig"},
        )
        Action.objects.all().delete()

        UpdateAgentChatChannelActionType.do(
            user, channel, name="Support v2", enabled=False
        )
        action = Action.objects.get()
        assert "xoxb-secret" not in str(action.params)
        assert "sig" not in str(action.params["original_values"]["config"])

        _undo(user, session_id, application)
        channel.refresh_from_db()
        assert channel.name == "Support"
        assert channel.enabled is True
        # Undoing kept the stored secrets.
        assert channel.config["bot_token"] == "xoxb-secret"
        _redo(user, session_id, application)
        channel.refresh_from_db()
        assert channel.name == "Support v2"
        Action.objects.all().delete()

        DeleteAgentChatChannelActionType.do(user, channel)
        assert not AgentChatChannel.objects.filter(id=channel.id).exists()
        _undo(user, session_id, application)
        assert AgentChatChannel.objects.filter(id=channel.id).exists()
        Action.objects.all().delete()

        web = CreateAgentChatChannelActionType.do(
            user, application, "web", config={"title": "Help"}
        )
        slug = web.config["slug"]
        Action.objects.all().delete()
        UpdateAgentChatChannelActionType.do(user, web, config={"title": "Help v2"})
        action = Action.objects.get()
        # The public link is not part of the undo history either.
        assert slug not in str(action.params)
        _undo(user, session_id, application)
        web.refresh_from_db()
    assert web.config["title"] == "Help"
    assert web.config["slug"] == slug


# ---------------------------------------------------------------------------
# Agent definition (skills were not undoable before)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_agent_definition_undo_covers_skills_and_skips_no_ops(setup):
    user, session_id, workspace, application, agent, table = setup
    skill = WorkspaceSkillHandler().create_skill(workspace, name="Tone")

    with patch(BROADCAST):
        UpdateAgentDefinitionActionType.do(
            user,
            agent.id,
            {"skills": [{"skill_id": skill.id, "mode": "on_demand"}]},
        )
        assert list(agent.agent_skills.values_list("skill_id", "mode")) == [
            (skill.id, "on_demand")
        ]
        _undo(user, session_id, application)
        assert agent.agent_skills.count() == 0
        _redo(user, session_id, application)
        assert agent.agent_skills.count() == 1

        Action.objects.all().delete()
        UpdateAgentDefinitionActionType.do(
            user, agent.id, {"skills": [{"skill_id": skill.id, "mode": "on_demand"}]}
        )
        UpdateAgentDefinitionActionType.do(user, agent.id, {"name": agent.name})
    assert Action.objects.count() == 0


# ---------------------------------------------------------------------------
# Audit log: conversations and approvals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_approval_decisions_and_chat_actions_are_audit_logged(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    chat = AgentChat.objects.create(
        agent=agent, user=user, title="Leads", status=AgentChat.Status.AWAITING_APPROVAL
    )
    approval = AgentChatToolApproval.objects.create(
        chat=chat, tool_call_id="c1", tool_name="send_email", tool_args={}
    )

    with (
        patch(BROADCAST),
        patch(
            "baserow_enterprise.agent_application.actions.AgentChatHandler"
            ".decide_tool_approvals",
            return_value=[approval],
        ),
    ):
        DecideAgentToolApprovalActionType.do(
            user,
            chat,
            [
                {
                    "id": approval.id,
                    "approved": True,
                    "reason": "",
                    "dont_ask_again": False,
                }
            ],
        )
    entry = AuditLogEntry.objects.get(action_type="decide_agent_tool_approval")
    assert entry.actor_id == user.id
    assert entry.params["approval_id"] == approval.id
    assert entry.params["tool_name"] == "send_email"
    assert entry.params["decision"] == "approved"
    assert entry.params["chat_uuid"] == str(chat.uuid)
    assert not Action.objects.filter(type="decide_agent_tool_approval").exists()

    chat.status = AgentChat.Status.IN_PROGRESS
    chat.save(update_fields=["status"])
    with patch(BROADCAST):
        CancelAgentChatRunActionType.do(user, chat)
    assert AuditLogEntry.objects.filter(action_type="cancel_agent_chat_run").exists()

    chat.status = AgentChat.Status.IDLE
    chat.save(update_fields=["status"])
    with patch(BROADCAST):
        DeleteAgentChatActionType.do(user, chat)
    entry = AuditLogEntry.objects.get(action_type="delete_agent_chat")
    assert entry.params["chat_title"] == "Leads"
    assert not AgentChat.objects.filter(id=chat.id).exists()


# The memory tool runs its database work in a thread, which needs committed data.
@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_agent_tool_dispatches_and_memory_writes_are_audited_as_the_agent(
    enterprise_data_fixture, synced_roles
):
    import asyncio
    from types import SimpleNamespace

    from baserow.core.agents.subjects import AgentSubjectType
    from baserow_enterprise.agent_application.actions import (
        DispatchAgentToolActionType,
        UpdateAgentMemoryActionType,
    )
    from baserow_enterprise.agent_application.tools.memory import remember

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    identity = AgentService().create_agent(user, workspace, name="Identity")
    chat = AgentChat.objects.create(agent=agent, user=user, title="Outreach")
    tool = AgentTool.objects.create(agent=agent, type="service", name="Mail")

    DispatchAgentToolActionType.do(identity, tool, "smtp_email", chat)
    entry = AuditLogEntry.objects.get(action_type="dispatch_agent_tool")
    assert entry.actor_type == AgentSubjectType.type
    assert entry.actor_id == identity.id
    assert entry.params["tool_name"] == "Mail"
    assert entry.params["service_type"] == "smtp_email"
    assert entry.params["chat_uuid"] == str(chat.uuid)
    assert not Action.objects.filter(type="dispatch_agent_tool").exists()

    agent.memory = "Remember the leads."
    UpdateAgentMemoryActionType.do(identity, agent, "appended")
    entry = AuditLogEntry.objects.get(action_type="update_agent_memory")
    assert entry.actor_id == identity.id
    assert entry.params["mode"] == "appended"
    assert entry.params["memory_length"] == len("Remember the leads.")
    # The memory text itself stays out of the audit log.
    assert "Remember the leads." not in str(entry.params)

    # A memory tool call of a run registers the entry on the way.
    agent.refresh_from_db()
    deps = SimpleNamespace(user=identity, agent=agent)
    with patch(BROADCAST):
        result = asyncio.run(remember(SimpleNamespace(deps=deps), "Note", "t"))
    assert result == {"success": True}
    assert AuditLogEntry.objects.filter(action_type="update_agent_memory").count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_skill_changes_are_audited(enterprise_data_fixture, synced_roles):
    from baserow.core.skills.actions import (
        CreateWorkspaceSkillActionType,
        DeleteWorkspaceSkillActionType,
        UpdateWorkspaceSkillActionType,
    )

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    skill = CreateWorkspaceSkillActionType.do(user, workspace, name="Tone")
    UpdateWorkspaceSkillActionType.do(user, skill, content="Be brief.")
    DeleteWorkspaceSkillActionType.do(user, skill)

    assert list(
        AuditLogEntry.objects.filter(action_type__endswith="_workspace_skill")
        .order_by("id")
        .values_list("action_type", flat=True)
    ) == ["create_workspace_skill", "update_workspace_skill", "delete_workspace_skill"]
    entry = AuditLogEntry.objects.get(action_type="delete_workspace_skill")
    assert entry.params["skill_name"] == "Tone"
    assert entry.params["workspace_id"] == workspace.id
