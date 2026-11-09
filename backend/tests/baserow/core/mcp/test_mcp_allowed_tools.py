import pytest

from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.exceptions import MCPToolsNotAvailable
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool, MCPToolRegistry, mcp_tool_registry


@pytest.mark.django_db
def test_endpoint_without_allow_list_gets_only_legacy_default_tools(data_fixture):
    class Legacy(MCPTool):
        """Legacy."""

        type = LEGACY_DEFAULT_TOOLS[0]

    class New(MCPTool):
        """New."""

        type = "brand_new_tool"

    registry = MCPToolRegistry()
    registry.register(Legacy())
    registry.register(New())
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=None)

    assert [t.name for t in registry.get_allowed_tools(endpoint)] == [
        LEGACY_DEFAULT_TOOLS[0]
    ]
    assert registry.get_allowed_tool(endpoint, "brand_new_tool") is None
    assert registry.get_allowed_tool(endpoint, LEGACY_DEFAULT_TOOLS[0]) is not None


# Removed in milestone 2. It was disabled from the day `allowed_tools` was
# added, so no stored list can hold it and no data migration is needed.
REMOVED_TOOLS = ["create_table"]
# Disabled before milestone 2 and now enabled under the same names.
REENABLED_TOOLS = ["create_fields", "update_fields", "delete_fields"]


@pytest.mark.parametrize("name", REMOVED_TOOLS)
def test_removed_tools_are_not_registered(name):
    assert name not in mcp_tool_registry.registry


@pytest.mark.django_db
@pytest.mark.parametrize("name", REMOVED_TOOLS)
def test_removed_tools_cannot_be_stored(data_fixture, name):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_tables"]
    )
    handler = MCPEndpointHandler()

    with pytest.raises(MCPToolsNotAvailable):
        handler.update_allowed_tools(user, endpoint, ["list_tables", name])
    with pytest.raises(MCPToolsNotAvailable):
        handler.grant_oauth_client(user, workspace, "client", "App", [name])

    endpoint.refresh_from_db()
    assert endpoint.allowed_tools == ["list_tables"]
    assert not MCPEndpoint.objects.filter(oauth_client_id="client").exists()


@pytest.mark.django_db
def test_new_endpoint_key_gets_no_new_write_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().create_endpoint(user, workspace, "Key")

    new_write_tools = REENABLED_TOOLS + [
        "create_tables",
        "create_views",
        "create_view_filters",
    ]
    assert not set(new_write_tools) & set(endpoint.allowed_tools)
    assert not set(new_write_tools) & set(LEGACY_DEFAULT_TOOLS)


@pytest.mark.django_db
def test_legacy_endpoint_gets_no_reenabled_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=None)

    enabled = {tool.name for tool in mcp_tool_registry.get_enabled_tools()}
    allowed = {tool.name for tool in mcp_tool_registry.get_allowed_tools(endpoint)}

    assert set(REENABLED_TOOLS) <= enabled
    assert not set(REENABLED_TOOLS) & allowed
