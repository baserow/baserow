"""Tests for the row tools shared by MCP and the Agent Builder."""

from typing import get_type_hints

from django.conf import settings
from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pydantic import TypeAdapter, ValidationError

from baserow.contrib.database.tools import rows
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext


@pytest.mark.django_db
def test_row_tools_over_mcp_keep_their_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()

    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.list_tools()
        finally:
            current_key.reset(token)

    with transaction.atomic():
        listed = async_to_sync(inner)()

    schemas = {tool.name: tool.inputSchema for tool in listed.tools}
    assert {
        name: (set(schemas[name]["properties"]), schemas[name]["required"])
        for name in ("list_table_rows", "create_rows", "update_rows", "delete_rows")
    } == {
        "list_table_rows": ({"table_id", "search", "page", "size"}, ["table_id"]),
        "create_rows": ({"table_id", "rows"}, ["table_id", "rows"]),
        "update_rows": ({"table_id", "rows"}, ["table_id", "rows"]),
        "delete_rows": ({"table_id", "row_ids"}, ["table_id", "row_ids"]),
    }
    # The REST API's batch limit.
    assert (
        schemas["delete_rows"]["properties"]["row_ids"]["maxItems"]
        == settings.BATCH_ROWS_SIZE_LIMIT
    )


@pytest.mark.django_db(transaction=True)
def test_create_rows_keeps_rich_text_mentions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    data_fixture.create_long_text_field(
        name="Notes", table=table, long_text_enable_rich_text=True
    )
    ctx = ToolContext(user=user, workspace=table.database.workspace)

    [created] = rows.create_rows(
        ctx, table.id, [{"Name": "Test", "Notes": f"Hello @{user.id} check this"}]
    )

    assert created["Name"] == "Test"
    assert f"@{user.id}" in created["Notes"]


@pytest.mark.parametrize(
    "function,arguments",
    [
        (rows.create_rows, {"table_id": 1, "rows": []}),
        (rows.update_rows, {"table_id": 1, "rows": []}),
        (rows.delete_rows, {"table_id": 1, "row_ids": []}),
    ],
)
def test_row_tools_refuse_empty_lists(function, arguments):
    name = next(key for key in arguments if key != "table_id")
    annotation = get_type_hints(function, include_extras=True)[name]
    with pytest.raises(ValidationError):
        TypeAdapter(annotation).validate_python(arguments[name])
