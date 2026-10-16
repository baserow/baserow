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


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_agent_application_actions_undo_redo(data_fixture, operation):
    session_id = "agent-application-session"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    if operation == "create":
        action_type = CreateApplicationActionType
        agent = action_type.do(user, workspace, "agent", name="Researcher")
    else:
        agent = data_fixture.create_agent_application(
            workspace=workspace, name="Researcher"
        )
        if operation == "update":
            action_type = UpdateApplicationActionType
            action_type.do(user, agent, name="Writer")
        else:
            action_type = DeleteApplicationActionType
            action_type.do(user, agent)
    other = data_fixture.create_agent_application(
        workspace=workspace, name="Independent"
    )
    action = Action.objects.get(type=action_type.type)
    assert action.params["application_type"] == "agent"
    assert action.params["application_id"] == agent.id

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
