import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    OrderApplicationsActionType,
    UpdateApplicationActionType,
)
from baserow.core.models import Application
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    assert_undo_redo_actions_fails_with_error,
)
from baserow_enterprise.agent.models import AgentApplication
from baserow_enterprise.audit_log.models import AuditLogEntry


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_agent_application_actions_undo_redo_and_audit_log(
    enterprise_data_fixture, enable_enterprise, synced_roles, operation
):
    session_id = "agent-application-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    workspace = enterprise_data_fixture.create_workspace(user=user)
    if operation == "create":
        action_type = CreateApplicationActionType
        agent = action_type.do(user, workspace, "agent", name="Researcher")
    else:
        agent = enterprise_data_fixture.create_agent_application(
            workspace=workspace, name="Researcher"
        )
        if operation == "update":
            action_type = UpdateApplicationActionType
            action_type.do(user, agent, name="Writer")
        else:
            action_type = DeleteApplicationActionType
            action_type.do(user, agent)
    other = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Independent"
    )
    action = Action.objects.get(type=action_type.type)
    assert action.params["application_type"] == "agent"
    assert action.params["application_id"] == agent.id
    audit = AuditLogEntry.objects.get(action_type=action_type.type)
    assert audit.user_id == user.id
    assert audit.workspace_id == workspace.id
    assert audit.action_params["application_id"] == agent.id
    assert "%(" not in audit.description

    scopes = [WorkspaceActionScopeType.value(workspace.id)]
    undone = ActionHandler.undo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(undone, [action_type])
    if operation == "create":
        assert not AgentApplication.objects.filter(id=agent.id).exists()
    else:
        agent.refresh_from_db()
        assert agent.name == "Researcher"
        assert not agent.trashed
    assert AgentApplication.objects.get(id=other.id).name == "Independent"

    redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(redone, [action_type])
    if operation == "delete":
        assert not AgentApplication.objects.filter(id=agent.id).exists()
    else:
        agent.refresh_from_db()
        assert not agent.trashed
        assert agent.name == ("Writer" if operation == "update" else "Researcher")
    assert AgentApplication.objects.get(id=other.id).name == "Independent"
    logs = AuditLogEntry.objects.filter(action_type=action_type.type).order_by("id")
    assert list(logs.values_list("action_command_type", flat=True)) == [
        "DO",
        "UNDO",
        "REDO",
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "delete"])
@pytest.mark.parametrize("command", ["undo", "redo"])
def test_agent_application_undo_redo_cannot_bypass_disabled_feature_flag(
    enterprise_data_fixture, settings, operation, command
):
    session_id = "agent-application-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    workspace = enterprise_data_fixture.create_workspace(user=user)
    if operation == "create":
        action_type = CreateApplicationActionType
        agent = action_type.do(user, workspace, "agent", name="Researcher")
    else:
        action_type = DeleteApplicationActionType
        agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
        action_type.do(user, agent)
    scopes = [WorkspaceActionScopeType.value(workspace.id)]
    if command == "redo":
        assert_undo_redo_actions_are_valid(
            ActionHandler.undo(user, scopes, session_id), [action_type]
        )
    agent.refresh_from_db()
    original_trashed = agent.trashed
    settings.FEATURE_FLAGS = []
    actions = getattr(ActionHandler, command)(user, scopes, session_id)
    assert_undo_redo_actions_fails_with_error(actions, [action_type])
    assert "FeatureDisabledException" in actions[0].error
    agent.refresh_from_db()
    assert agent.trashed == original_trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("command", ["undo", "redo"])
def test_agent_order_undo_redo_cannot_bypass_disabled_feature_flag(
    enterprise_data_fixture, settings, command
):
    session_id = "agent-order-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    agent = enterprise_data_fixture.create_agent_application(user=user, order=2)
    database = enterprise_data_fixture.create_database_application(
        workspace=agent.workspace, order=1
    )
    OrderApplicationsActionType.do(user, agent.workspace, [agent.id, database.id])
    scopes = [WorkspaceActionScopeType.value(agent.workspace_id)]
    if command == "redo":
        assert_undo_redo_actions_are_valid(
            ActionHandler.undo(user, scopes, session_id), [OrderApplicationsActionType]
        )
    original_order = list(
        Application.objects.filter(workspace=agent.workspace).values_list("id", "order")
    )
    settings.FEATURE_FLAGS = []
    actions = getattr(ActionHandler, command)(user, scopes, session_id)
    assert_undo_redo_actions_fails_with_error(actions, [OrderApplicationsActionType])
    assert "FeatureDisabledException" in actions[0].error
    assert (
        list(
            Application.objects.filter(workspace=agent.workspace).values_list(
                "id", "order"
            )
        )
        == original_order
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_application_order_undo_redo_keeps_disabled_agent_in_full_order(
    enterprise_data_fixture, settings
):
    session_id = "application-order-session"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    agent = enterprise_data_fixture.create_agent_application(user=user, order=2)
    first = enterprise_data_fixture.create_database_application(
        workspace=agent.workspace, order=1
    )
    second = enterprise_data_fixture.create_database_application(
        workspace=agent.workspace, order=3
    )
    settings.FEATURE_FLAGS = []
    OrderApplicationsActionType.do(user, agent.workspace, [second.id, first.id])
    action = Action.objects.get(type=OrderApplicationsActionType.type)
    assert action.params["original_application_ids"] == [first.id, second.id]
    assert action.params["application_ids"] == [second.id, first.id]
    assert list(
        Application.objects.filter(workspace=agent.workspace).values_list("id", "order")
    ) == [(agent.id, 1), (second.id, 2), (first.id, 3)]
    scopes = [WorkspaceActionScopeType.value(agent.workspace_id)]
    assert_undo_redo_actions_are_valid(
        ActionHandler.undo(user, scopes, session_id), [OrderApplicationsActionType]
    )
    assert list(
        Application.objects.filter(workspace=agent.workspace).values_list("id", "order")
    ) == [(agent.id, 1), (first.id, 2), (second.id, 3)]
    assert_undo_redo_actions_are_valid(
        ActionHandler.redo(user, scopes, session_id), [OrderApplicationsActionType]
    )
    assert list(
        Application.objects.filter(workspace=agent.workspace).values_list("id", "order")
    ) == [(agent.id, 1), (second.id, 2), (first.id, 3)]
