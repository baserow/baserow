import string

import pytest

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.exceptions import (
    MaximumUniqueEndpointTriesError,
    MCPEndpointDoesNotBelongToUser,
    MCPEndpointDoesNotExist,
    MCPToolsNotAvailable,
)
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import mcp_tool_registry


@pytest.mark.django_db
def test_get_endpoint(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user=user, endpoint_id=99999)

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user=user_2, endpoint_id=endpoint.id)

    with pytest.raises(UserNotInWorkspace):
        handler.get_endpoint(user=user, endpoint_id=endpoint_2.id)

    endpoint_tmp = handler.get_endpoint(user, endpoint.id)
    assert endpoint_tmp.id == endpoint.id
    assert endpoint.workspace_id == workspace_1.id
    assert isinstance(endpoint_tmp, MCPEndpoint)

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_endpoint(
            user=user,
            endpoint_id=endpoint.id,
            base_queryset=MCPEndpoint.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db
def test_get_endpoint_does_not_return_oauth_grants(data_fixture):
    user = data_fixture.create_user()
    grant = data_fixture.create_mcp_endpoint(
        user=user, oauth_client_id="https://claude.ai/x.json"
    )
    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user, grant.id)
    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user, grant.id, base_queryset=MCPEndpoint.objects.all())


@pytest.mark.django_db
def test_generate_unique_key(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    handler = MCPEndpointHandler()

    assert len(handler.generate_unique_key(32)) == 32
    assert len(handler.generate_unique_key(10)) == 10
    assert handler.generate_unique_key(32) != handler.generate_unique_key(32)

    key = handler.generate_unique_key(32)
    assert not MCPEndpoint.objects.filter(key=key).exists()

    for char in string.ascii_letters + string.digits:
        data_fixture.create_mcp_endpoint(key=char, user=user, workspace=workspace)

    with pytest.raises(MaximumUniqueEndpointTriesError):
        handler.generate_unique_key(1, 3)


@pytest.mark.django_db
def test_create_endpoint(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    handler = MCPEndpointHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.create_endpoint(user=user, workspace=workspace_2, name="Test")

    endpoint = handler.create_endpoint(user=user, workspace=workspace_1, name="Test")
    assert endpoint.user_id == user.id
    assert endpoint.workspace_id == workspace_1.id
    assert endpoint.name == "Test"
    assert len(endpoint.key) == 32

    assert MCPEndpoint.objects.all().count() == 1


@pytest.mark.django_db
def test_create_endpoint_stores_read_only_and_legacy_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().create_endpoint(user, workspace, "Test")

    expected = [
        tool.name
        for tool in mcp_tool_registry.get_enabled_tools()
        if (tool.read_only and not tool.off_by_default)
        or tool.name in LEGACY_DEFAULT_TOOLS
    ]
    assert endpoint.allowed_tools == expected
    assert set(LEGACY_DEFAULT_TOOLS) <= set(expected)
    endpoint.refresh_from_db()
    assert endpoint.allowed_tools == expected


@pytest.mark.django_db
def test_update_endpoint(data_fixture):
    user = data_fixture.create_user()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user)
    endpoint_2 = data_fixture.create_mcp_endpoint()

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        handler.update_endpoint(user=user, endpoint=endpoint_2, name="New")

    endpoint_1 = handler.update_endpoint(user=user, endpoint=endpoint_1, name="New")
    assert endpoint_1.name == "New"

    endpoint_1 = MCPEndpoint.objects.get(pk=endpoint_1.id)
    assert endpoint_1.name == "New"


@pytest.mark.django_db
def test_delete_endpoint(data_fixture):
    user = data_fixture.create_user()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user)
    endpoint_2 = data_fixture.create_mcp_endpoint()

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        handler.delete_endpoint(user=user, endpoint=endpoint_2)

    handler.delete_endpoint(user=user, endpoint=endpoint_1)

    assert MCPEndpoint.objects.all().count() == 1
    assert MCPEndpoint.objects.all().first().id == endpoint_2.id


@pytest.mark.django_db
def test_update_allowed_tools(data_fixture):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, allowed_tools=["list_tables"]
    )
    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        handler.update_allowed_tools(other, endpoint, ["list_databases"])
    with pytest.raises(MCPToolsNotAvailable) as error:
        handler.update_allowed_tools(user, endpoint, ["list_databases", "nope"])
    assert error.value.names == ["nope"]
    endpoint.refresh_from_db()
    assert endpoint.allowed_tools == ["list_tables"]

    handler.update_allowed_tools(user, endpoint, ["list_tables", "list_databases"])
    endpoint.refresh_from_db()
    assert endpoint.allowed_tools == ["list_databases", "list_tables"]
