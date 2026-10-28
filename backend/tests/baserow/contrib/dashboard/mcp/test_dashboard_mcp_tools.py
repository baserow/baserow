"""The dashboard tools over MCP."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.registries import mcp_tool_registry

READ_TOOLS = ["list_dashboards", "list_widgets", "get_widget_data"]
EDIT_TOOLS = ["create_dashboards", "create_widgets", "update_widgets"]
DELETE_TOOLS = ["delete_widgets"]
ALL_TOOLS = [*READ_TOOLS, *EDIT_TOOLS, *DELETE_TOOLS]
KUMA_ONLY = ("ask_user", "navigate", "switch_mode", "load_row_tools", "$formula:")


def _session(endpoint, callback):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await callback(client)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _call(endpoint, name, arguments):
    async def callback(client):
        return await client.call_tool(name, arguments)

    return _session(endpoint, callback)


def _json(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


@pytest.fixture
def amount_table(data_fixture):
    def make(workspace):
        database = data_fixture.create_database_application(workspace=workspace)
        table = data_fixture.create_database_table(database=database)
        amount = data_fixture.create_number_field(table=table, name="Amount")
        model = table.get_model()
        model.objects.create(**{f"field_{amount.id}": 2})
        model.objects.create(**{f"field_{amount.id}": 3})
        return table, amount

    return make


def test_legacy_endpoints_get_no_dashboard_tools():
    assert not set(ALL_TOOLS) & set(LEGACY_DEFAULT_TOOLS)


@pytest.mark.django_db
def test_endpoint_without_allow_list_gets_no_dashboard_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=None)

    allowed = {tool.name for tool in mcp_tool_registry.get_allowed_tools(endpoint)}

    assert not set(ALL_TOOLS) & allowed


@pytest.mark.django_db
def test_dashboard_tools_over_mcp(data_fixture, amount_table):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)
    table, amount = amount_table(endpoint.workspace)

    async def callback(client):
        listed = await client.list_tools()
        dashboard = _json(
            await client.call_tool("create_dashboards", {"names": ["Sales"]})
        )["created"][0]
        created = _json(
            await client.call_tool(
                "create_widgets",
                {
                    "dashboard_id": dashboard["id"],
                    "widgets": [
                        {
                            "type": "summary",
                            "title": "Total",
                            "table_id": table.id,
                            "field_id": amount.id,
                            "aggregation_type": "sum",
                        }
                    ],
                },
            )
        )
        widget_id = created["created"][0]["id"]
        dashboards = _json(await client.call_tool("list_dashboards", {}))
        data = _json(
            await client.call_tool("get_widget_data", {"widget_ids": [widget_id]})
        )
        updated = _json(
            await client.call_tool(
                "update_widgets",
                {"widgets": [{"widget_id": widget_id, "aggregation_type": "max"}]},
            )
        )
        widgets = _json(
            await client.call_tool("list_widgets", {"dashboard_id": dashboard["id"]})
        )
        deleted = _json(
            await client.call_tool("delete_widgets", {"widget_ids": [widget_id]})
        )
        return listed, dashboards, data, updated, widgets, deleted, widget_id

    listed, dashboards, data, updated, widgets, deleted, widget_id = _session(
        endpoint, callback
    )

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == set(ALL_TOOLS)
    for tool in tools.values():
        for kuma_only in KUMA_ONLY:
            assert kuma_only not in tool.description, tool.name
    assert dashboards["dashboards"][0]["widget_count"] == 1
    assert data["widgets"] == [
        {"widget_id": widget_id, "configured": True, "data": {"result": "5"}}
    ]
    assert updated["updated"][0]["aggregation_type"] == "max"
    assert widgets["widgets"][0]["aggregation_type"] == "max"
    assert deleted == {"deleted": [widget_id], "errors": []}
    assert Widget.objects_and_trash.get(id=widget_id).trashed


@pytest.mark.django_db
def test_chart_without_licence_reports_licence_over_mcp(data_fixture, amount_table):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)
    dashboard = data_fixture.create_dashboard_application(workspace=endpoint.workspace)
    table, amount = amount_table(endpoint.workspace)

    result = _json(
        _call(
            endpoint,
            "create_widgets",
            {
                "dashboard_id": dashboard.id,
                "widgets": [
                    {
                        "type": "chart",
                        "title": "Chart",
                        "table_id": table.id,
                        "series": [{"field_id": amount.id, "aggregation_type": "sum"}],
                    }
                ],
            },
        )
    )

    assert result["created"] == []
    error = result["errors"][0]["error"]
    assert error != "Internal error."
    assert "licen" in error.lower() or "feature" in error.lower()


@pytest.mark.django_db
def test_dashboard_tools_over_mcp_hide_other_workspaces(data_fixture, amount_table):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)
    elsewhere = data_fixture.create_workspace(user=endpoint.user)
    foreign_dashboard = data_fixture.create_dashboard_application(workspace=elsewhere)
    foreign_widget = data_fixture.create_summary_widget(dashboard=foreign_dashboard)

    listed = _call(endpoint, "list_widgets", {"dashboard_id": foreign_dashboard.id})
    assert listed.isError is True
    assert listed.content[0].text == "Not found in this workspace."
    deleted = _json(
        _call(endpoint, "delete_widgets", {"widget_ids": [foreign_widget.id]})
    )
    assert deleted["errors"][0]["error"] == "Not found in this workspace."
    assert not Widget.objects_and_trash.get(id=foreign_widget.id).trashed


@pytest.mark.django_db
@pytest.mark.parametrize("name", ALL_TOOLS)
def test_dashboard_tools_over_mcp_reject_unknown_arguments(data_fixture, name):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)

    result = _call(endpoint, name, {"thought": "why"})

    assert result.isError is True
    assert "thought" in result.content[0].text
