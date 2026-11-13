from unittest.mock import patch

from django.urls import reverse

import pytest

from baserow.core.exceptions import PermissionDenied
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    cimd_client,
    fake_cimd_fetch,
    pkce_pair,
)


def _member(enterprise_data_fixture, workspace_role, database_role=None):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        custom_permissions=[(user, workspace_role)]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    if database_role:
        RoleAssignmentHandler().assign_role(
            user, workspace, Role.objects.get(uid=database_role), database
        )
    return user, workspace


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_role", ["NO_ROLE_LOW_PRIORITY", "NO_ACCESS"])
def test_member_with_only_a_database_role_can_manage_mcp_endpoints(
    enterprise_data_fixture, enable_enterprise, synced_roles, workspace_role
):
    user, workspace = _member(enterprise_data_fixture, workspace_role, "VIEWER")
    handler = MCPEndpointHandler()

    _, created = handler.grant_oauth_client(user, workspace, "client", "App", [])
    assert created
    _, created = handler.grant_oauth_client(user, workspace, "client", "App", [])
    assert not created

    endpoint = handler.create_endpoint(user, workspace, "Key")
    assert handler.get_endpoint(user, endpoint.id) == endpoint
    assert handler.update_endpoint(user, endpoint, "Renamed").name == "Renamed"
    handler.delete_endpoint(user, endpoint)


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_role", ["NO_ROLE_LOW_PRIORITY", "NO_ACCESS"])
def test_member_without_any_role_cannot_create_mcp_endpoints(
    enterprise_data_fixture, enable_enterprise, synced_roles, workspace_role
):
    user, workspace = _member(enterprise_data_fixture, workspace_role)
    handler = MCPEndpointHandler()

    with pytest.raises(PermissionDenied):
        handler.grant_oauth_client(user, workspace, "client", "App", [])
    with pytest.raises(PermissionDenied):
        handler.create_endpoint(user, workspace, "Key")


@pytest.mark.django_db
@patch("baserow.core.mcp.oauth.cimd.MCPMetadataFetcher.download", fake_cimd_fetch)
def test_consent_page_counts_only_databases_the_member_can_see(
    client, api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, workspace = _member(enterprise_data_fixture, "NO_ROLE_LOW_PRIORITY", "VIEWER")
    enterprise_data_fixture.create_database_application(workspace=workspace)
    token = enterprise_data_fixture.generate_token(user)
    _, challenge = pkce_pair()

    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(cimd_client(client), challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    assert response.json()["workspaces"] == [
        {"id": workspace.id, "name": workspace.name, "database_count": 1}
    ]
