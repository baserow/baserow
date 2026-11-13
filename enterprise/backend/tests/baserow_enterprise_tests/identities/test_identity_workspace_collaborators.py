from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.identities.operations import ListIdentitiesWorkspaceOperationType
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db
def test_workspace_identity_metadata_is_minimal_visible_to_viewer_and_batched(
    data_fixture, api_client, enable_enterprise, synced_roles
):
    viewer, token = data_fixture.create_user_and_token()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[viewer])
    roles = RoleAssignmentHandler()
    roles.assign_role(viewer, workspace, roles.get_role_by_uid("VIEWER"))
    identity = data_fixture.create_identity(workspace=workspace, name="Ops")
    data_fixture.create_identity(workspace=workspace, trashed=True)
    data_fixture.create_identity(workspace=workspace, is_active=False)
    assert not CoreHandler().check_permissions(
        viewer,
        ListIdentitiesWorkspaceOperationType.type,
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
    assert body["identities"] == [
        {"id": identity.id, "name": "Ops", "user_type": "identity"}
    ]
    assert {person["user_id"] for person in body["users"]} == {admin.id, viewer.id}
    for index in range(5):
        data_fixture.create_identity(workspace=workspace, name=f"Identity {index}")
    with CaptureQueriesContext(connection) as many:
        response = api_client.get(url, **headers)
    assert len(response.json()[0]["identities"]) == 6
    assert len(few) == len(many)
