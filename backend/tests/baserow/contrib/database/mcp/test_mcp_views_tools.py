"""Tests for list_views, the first tool shared with Kuma over MCP."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.tools.views import list_views
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.tools import ToolContext


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


@pytest.mark.django_db
def test_list_views_over_mcp(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["list_views"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, name="All")

    async def callback(client):
        listed = await client.list_tools()
        result = await client.call_tool("list_views", {"table_id": table.id})
        return listed, result

    listed, result = _session(endpoint, callback)

    tool = next(t for t in listed.tools if t.name == "list_views")
    assert tool.annotations.readOnlyHint is True
    assert set(tool.inputSchema["properties"]) == {"table_id"}
    assert tool.inputSchema["required"] == ["table_id"]
    assert "List the views of a table" in tool.description
    assert result.isError is False
    assert json.loads(result.content[0].text) == {
        "views": [
            {
                "id": view.id,
                "name": "All",
                "public": False,
                "type": "grid",
                "row_height": "small",
                "sorts": [],
                "filters": [],
                "filter_type": "AND",
                "filter_groups": [],
                "row_colours": [],
                "hidden_field_ids": [],
            }
        ]
    }


@pytest.mark.django_db
def test_list_views_rejects_unknown_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["list_views"])

    async def callback(client):
        return await client.call_tool("list_views", {"table_id": 1, "thought": "x"})

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "thought" in result.content[0].text


@pytest.mark.django_db
def test_list_views_table_in_other_workspace_is_not_found(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["list_views"])
    other = data_fixture.create_database_table(user=endpoint.user)

    async def callback(client):
        return await client.call_tool("list_views", {"table_id": other.id})

    result = _session(endpoint, callback)

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."


@pytest.mark.django_db
def test_endpoint_without_allow_list_does_not_get_list_views(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=None)

    assert mcp_tool_registry.get_allowed_tool(endpoint, "list_views") is None


@pytest.mark.django_db
def test_shared_list_views_reports_status(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    statuses = []

    result = list_views(ToolContext(user, workspace, statuses.append), table.id)

    assert result == {"views": []}
    assert statuses == ["Listing views in Tasks..."]


@pytest.mark.django_db
def test_shared_list_views_loads_form_options_in_one_query(data_fixture):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from baserow.contrib.database.tools.views import ViewItem

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    ctx = ToolContext(user, workspace)

    def count_queries():
        with CaptureQueriesContext(connection) as queries:
            result = list_views(ctx, table.id)
        return len(queries), result

    form = data_fixture.create_form_view(table=table)
    data_fixture.create_form_view_field_option(form, field, enabled=True)
    count_queries()  # Warms the caches the first call fills.
    one_form, _ = count_queries()
    for _ in range(3):
        other = data_fixture.create_form_view(table=table)
        data_fixture.create_form_view_field_option(other, field, enabled=True)
    four_forms, result = count_queries()

    assert four_forms == one_form
    first = next(v for v in result["views"] if v["id"] == form.id)
    assert first == {
        **ViewItem.from_django_orm(form).model_dump(),
        "sorts": [],
        "filters": [],
        "filter_type": "AND",
        "filter_groups": [],
        "row_colours": [],
    }
    assert [o["field_id"] for o in first["field_options"]] == [field.id]
