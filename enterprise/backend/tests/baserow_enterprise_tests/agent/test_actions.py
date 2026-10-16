import pytest

from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.actions import (
    CreateApplicationActionType,
    DeleteApplicationActionType,
    UpdateApplicationActionType,
)
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
)
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
