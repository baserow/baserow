from django.shortcuts import reverse

import pytest

from baserow.core.mcp.groups import (
    AREA_AUTOMATION,
    GROUP_AUTOMATION_DELETE,
    GROUP_AUTOMATION_EDIT,
    GROUP_AUTOMATION_READ,
    GROUP_DATABASE_DELETE,
    GROUP_DATABASE_EDIT,
    GROUP_DATABASE_READ,
    MCPToolGroup,
    MCPToolGroupRegistry,
    mcp_tool_group_registry,
)
from baserow.core.mcp.registries import mcp_tool_registry
from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    cimd_client,
    pkce_pair,
)


def test_every_tool_has_a_registered_group():
    # Disabled tools too, so a tool can't be turned on without a group.
    groups = {group.type for group in mcp_tool_group_registry.get_all()}
    ungrouped = [
        tool.name for tool in mcp_tool_registry.get_all() if tool.group not in groups
    ]
    assert ungrouped == []


def test_core_database_tool_groups():
    groups = {tool.name: tool.group for tool in mcp_tool_registry.get_all()}
    assert groups["list_databases"] == GROUP_DATABASE_READ
    assert groups["list_applications"] == GROUP_DATABASE_READ
    assert groups["list_tables"] == GROUP_DATABASE_READ
    assert groups["get_table_schema"] == GROUP_DATABASE_READ
    assert groups["list_table_rows"] == GROUP_DATABASE_READ
    assert groups["create_rows"] == GROUP_DATABASE_EDIT
    assert groups["update_rows"] == GROUP_DATABASE_EDIT
    assert groups["create_tables"] == GROUP_DATABASE_EDIT
    assert groups["update_table"] == GROUP_DATABASE_EDIT
    assert groups["create_fields"] == GROUP_DATABASE_EDIT
    assert groups["update_fields"] == GROUP_DATABASE_EDIT
    assert groups["create_views"] == GROUP_DATABASE_EDIT
    assert groups["create_view_filters"] == GROUP_DATABASE_EDIT
    assert groups["delete_rows"] == GROUP_DATABASE_DELETE
    assert groups["delete_table"] == GROUP_DATABASE_DELETE
    assert groups["delete_fields"] == GROUP_DATABASE_DELETE
    assert "create_database" not in groups
    assert "create_table" not in groups


def test_core_automation_tool_groups():
    groups = {tool.name: tool.group for tool in mcp_tool_registry.get_all()}
    assert groups["list_workflows"] == GROUP_AUTOMATION_READ
    assert groups["list_nodes"] == GROUP_AUTOMATION_READ
    assert groups["create_workflows"] == GROUP_AUTOMATION_EDIT
    assert groups["add_nodes"] == GROUP_AUTOMATION_EDIT
    assert groups["update_nodes"] == GROUP_AUTOMATION_EDIT
    assert groups["delete_nodes"] == GROUP_AUTOMATION_DELETE
    for group in (
        GROUP_AUTOMATION_READ,
        GROUP_AUTOMATION_EDIT,
        GROUP_AUTOMATION_DELETE,
    ):
        assert mcp_tool_group_registry.get(group).area == AREA_AUTOMATION


def test_read_only_preset_groups_hold_only_read_only_tools():
    preset = {g.type for g in mcp_tool_group_registry.get_all() if g.read_only_preset}
    assert GROUP_DATABASE_READ in preset
    assert GROUP_DATABASE_EDIT not in preset
    assert GROUP_DATABASE_DELETE not in preset
    # Automations are turned on in Settings, not by the preset.
    assert GROUP_AUTOMATION_READ not in preset
    for tool in mcp_tool_registry.get_all():
        if tool.group in preset:
            assert tool.read_only, tool.name


def test_groups_are_returned_in_order():
    class Second(MCPToolGroup):
        type = "second"
        title = "Second"
        area = "database"
        order = 20

    class First(MCPToolGroup):
        type = "first"
        title = "First"
        area = "database"
        order = 10

    registry = MCPToolGroupRegistry()
    registry.register(Second())
    registry.register(First())
    assert [group.type for group in registry.get_ordered()] == ["first", "second"]


def _consent(client, api_client, token):
    _, challenge = pkce_pair()
    return api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(cimd_client(client), challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    ).json()


@pytest.mark.django_db
def test_consent_returns_the_groups_of_the_listed_tools_in_order(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    data = _consent(client, api_client, token)

    listed = {tool["group"] for tool in data["tools"]}
    expected = [
        {
            "type": group.type,
            "title": group.title,
            "area": group.area,
            "read_only_preset": group.read_only_preset,
        }
        for group in mcp_tool_group_registry.get_ordered()
        if group.type in listed
    ]
    assert data["groups"] == expected
    types = [group["type"] for group in data["groups"]]
    assert types.index(GROUP_DATABASE_READ) < types.index(GROUP_DATABASE_EDIT)
    assert types.index(GROUP_DATABASE_EDIT) < types.index(GROUP_DATABASE_DELETE)
