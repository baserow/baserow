import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.scopes import (
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    UpdateApplicationActionType,
)
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    assert_undo_redo_actions_fails_with_error,
)
from baserow_enterprise.agent_builder.actions import (
    CreateAgentActionType,
    DeleteAgentActionType,
    OrderAgentsActionType,
    UpdateAgentActionType,
)
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_agent_actions_undo_redo_and_audit_log(
    enterprise_data_fixture, enable_enterprise, synced_roles, operation
):
    session_id = "agent-builder-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    builder = enterprise_data_fixture.create_agent_builder_application(
        user=user, name="Agent team"
    )
    if operation == "create":
        action_type = CreateAgentActionType
        agent = action_type.do(user, builder.id, {"name": "Researcher"})
    else:
        agent = enterprise_data_fixture.create_agent_definition(
            agent_builder=builder, name="Researcher"
        )
        if operation == "update":
            action_type = UpdateAgentActionType
            action_type.do(user, agent.id, {"name": "Writer"})
        else:
            action_type = DeleteAgentActionType
            action_type.do(user, agent.id)

    audit = AuditLogEntry.objects.get(action_type=action_type.type)
    assert audit.user_id == user.id
    assert audit.workspace_id == builder.workspace_id
    assert audit.action_params["agent_id"] == agent.id
    assert audit.action_params["agent_builder_id"] == builder.id
    assert "Researcher" in audit.description or "Writer" in audit.description
    assert "%(" not in audit.description

    scopes = [ApplicationActionScopeType.value(builder.id)]
    undone = ActionHandler.undo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(undone, [action_type])
    if operation == "create":
        assert not AgentDefinition.objects.filter(id=agent.id).exists()
    else:
        agent.refresh_from_db()
        assert agent.name == "Researcher"
        assert not agent.trashed

    redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [action_type])
    if operation == "delete":
        assert not AgentDefinition.objects.filter(id=agent.id).exists()
    else:
        agent.refresh_from_db()
        assert agent.name == ("Writer" if operation == "update" else "Researcher")
        assert not agent.trashed

    logs = AuditLogEntry.objects.filter(action_type=action_type.type).order_by("id")
    assert list(logs.values_list("action_command_type", flat=True)) == [
        "DO",
        "UNDO",
        "REDO",
    ]
    assert logs.count() == 3


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_core_application_actions_support_agent_builder_and_preserve_children(
    enterprise_data_fixture, enable_enterprise, synced_roles, operation
):
    session_id = "agent-builder-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    workspace = enterprise_data_fixture.create_workspace(user=user)
    if operation == "create":
        action_type = CreateApplicationActionType
        builder = action_type.do(user, workspace, "agent_builder", name="Agent team")
        assert not builder.agents.exists()
    else:
        builder = enterprise_data_fixture.create_agent_builder_application(
            workspace=workspace, name="Agent team"
        )
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Researcher"
    )
    if operation == "update":
        action_type = UpdateApplicationActionType
        action_type.do(user, builder, name="Renamed team")
    elif operation == "delete":
        action_type = DeleteApplicationActionType
        action_type.do(user, builder)

    assert (
        Action.objects.get(type=action_type.type).params["application_type"]
        == "agent_builder"
    )
    scopes = [WorkspaceActionScopeType.value(workspace.id)]
    undone = ActionHandler.undo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(undone, [action_type])
    if operation == "create":
        assert not AgentBuilder.objects.filter(id=builder.id).exists()
        assert not AgentDefinition.objects.filter(id=agent.id).exists()
    else:
        builder.refresh_from_db()
        assert builder.name == "Agent team"
        assert not builder.trashed
        assert builder.agents.get() == agent

    redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [action_type])
    if operation == "delete":
        assert not AgentBuilder.objects.filter(id=builder.id).exists()
        assert not AgentDefinition.objects.filter(id=agent.id).exists()
    else:
        builder.refresh_from_db()
        assert not builder.trashed
        assert builder.name == (
            "Renamed team" if operation == "update" else "Agent team"
        )
        assert builder.agents.get() == agent
    assert AuditLogEntry.objects.filter(action_type=action_type.type).count() == 3


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_reorder_agents_undo_redo(enterprise_data_fixture):
    session_id = "agent-builder-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    first = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    second = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=2
    )
    OrderAgentsActionType.do(user, builder.id, [second.id, first.id])
    assert list(builder.agents.values_list("id", flat=True)) == [second.id, first.id]
    scopes = [ApplicationActionScopeType.value(builder.id)]
    assert_undo_redo_actions_are_valid(
        ActionHandler.undo(user, scopes, session_id), [OrderAgentsActionType]
    )
    assert list(builder.agents.values_list("id", flat=True)) == [first.id, second.id]
    assert_undo_redo_actions_are_valid(
        ActionHandler.redo(user, scopes, session_id), [OrderAgentsActionType]
    )
    assert list(builder.agents.values_list("id", flat=True)) == [second.id, first.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "delete"])
def test_application_undo_cannot_bypass_disabled_feature_flag(
    enterprise_data_fixture, settings, operation
):
    session_id = "agent-builder-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    workspace = enterprise_data_fixture.create_workspace(user=user)
    if operation == "create":
        action_type = CreateApplicationActionType
        builder = action_type.do(user, workspace, "agent_builder", name="Team")
    else:
        action_type = DeleteApplicationActionType
        builder = enterprise_data_fixture.create_agent_builder_application(
            workspace=workspace
        )
        action_type.do(user, builder)
    settings.FEATURE_FLAGS = []
    undone = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace.id)], session_id
    )
    assert_undo_redo_actions_fails_with_error(undone, [action_type])
    assert "FeatureDisabledException" in undone[0].error
    builder.refresh_from_db()
    assert builder.trashed == (operation == "delete")
