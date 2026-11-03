from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.core.agents.operations import ListAgentsWorkspaceOperationType
from baserow.core.handler import CoreHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db
def test_workspace_agent_metadata_is_minimal_visible_to_viewer_and_batched(
    data_fixture, api_client, enable_enterprise, synced_roles
):
    viewer, token = data_fixture.create_user_and_token()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[viewer])
    roles = RoleAssignmentHandler()
    roles.assign_role(viewer, workspace, roles.get_role_by_uid("VIEWER"))
    agent = data_fixture.create_agent(workspace=workspace, name="Ops")
    data_fixture.create_agent(workspace=workspace, trashed=True)
    data_fixture.create_agent(workspace=workspace, is_active=False)
    assert not CoreHandler().check_permissions(
        viewer,
        ListAgentsWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    url = reverse("api:workspaces:list")
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    api_client.get(url, **headers)
    with CaptureQueriesContext(connection) as few:
        response = api_client.get(url, **headers)
    assert response.status_code == 200
    body = response.json()[0]
    assert body["agents"] == [{"id": agent.id, "name": "Ops", "identity_type": "agent"}]
    assert {person["user_id"] for person in body["users"]} == {admin.id, viewer.id}
    for index in range(5):
        data_fixture.create_agent(workspace=workspace, name=f"Agent {index}")
    with CaptureQueriesContext(connection) as many:
        response = api_client.get(url, **headers)
    assert len(response.json()[0]["agents"]) == 6
    assert len(few) == len(many)
