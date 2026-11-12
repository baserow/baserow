import pytest

from baserow.core.exceptions import PermissionDenied
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


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
