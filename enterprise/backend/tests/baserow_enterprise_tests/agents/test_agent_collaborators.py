from django.urls import reverse

import pytest

from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db
def test_viewer_sees_only_minimal_agent_collaborators_in_workspace_list(
    data_fixture, api_client, enable_enterprise, synced_roles
):
    viewer, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(
        user=data_fixture.create_user(), members=[viewer]
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(viewer, workspace, roles.get_role_by_uid("VIEWER"))
    agent = data_fixture.create_agent(
        workspace=workspace, name="Ops", role_uid="EDITOR"
    )
    legacy = data_fixture.create_agent(workspace=workspace, name="Legacy")
    Agent.objects.filter(id=legacy.id).update(user=None)
    trashed = data_fixture.create_agent(workspace=workspace, name="Trashed")
    Agent.objects.filter(id=trashed.id).update(trashed=True)
    data_fixture.create_agent(name="Another workspace")

    assert not CoreHandler().check_permissions(
        viewer,
        ListAgentsWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    response = api_client.get(
        reverse("api:workspaces:list"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 200
    assert response.json()[0]["agents"] == [
        {"id": agent.id, "user_id": agent.user_id, "name": "Ops"}
    ]
