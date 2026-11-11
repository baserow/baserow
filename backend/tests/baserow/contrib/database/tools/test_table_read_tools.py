"""Tests for the table read tools shared by MCP and Kuma."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.tools.tables import get_table_schema, list_tables
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


@pytest.fixture
def two_databases(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    sales = data_fixture.create_database_application(workspace=workspace, name="Sales")
    hr = data_fixture.create_database_application(workspace=workspace, name="HR")
    orders = data_fixture.create_database_table(database=sales, name="Orders")
    customers = data_fixture.create_database_table(database=sales, name="Customers")
    staff = data_fixture.create_database_table(database=hr, name="Staff")
    # Another workspace of the same user must stay hidden.
    data_fixture.create_database_table(user=user, name="Elsewhere")
    return ToolContext(user=user, workspace=workspace), orders, customers, staff


@pytest.mark.django_db
def test_list_tables_lists_the_workspace_tables(two_databases):
    ctx, orders, customers, staff = two_databases

    result = list_tables(ctx)

    assert result == [
        {
            "id": table.id,
            "name": table.name,
            "order": table.order,
            "database_id": table.database_id,
            "database_name": table.database.name,
        }
        for table in (orders, customers, staff)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"database_name": "sal"}, ["Orders", "Customers"]),
        ({"table_names": ["cust", "staff"]}, ["Customers", "Staff"]),
        ({"database_name": "Sales", "table_names": ["Staff"]}, []),
    ],
)
def test_list_tables_filters(two_databases, filters, expected):
    ctx, *_ = two_databases

    assert [table["name"] for table in list_tables(ctx, **filters)] == expected


@pytest.mark.django_db
def test_list_tables_matches_table_ids_or_names(two_databases):
    ctx, orders, customers, staff = two_databases

    result = list_tables(
        ctx,
        database_id=orders.database_id,
        table_ids=[orders.id, staff.id],
        table_names=["Customers"],
    )

    assert [table["id"] for table in result] == [orders.id, customers.id]


@pytest.mark.django_db
def test_list_tables_over_mcp_keeps_the_list_shape(data_fixture):
    # An endpoint without an allow-list gets the legacy tools, list_tables among them.
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(
        workspace=endpoint.workspace, name="Sales"
    )
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=endpoint.workspace)
    )

    result = _call(endpoint, "list_tables", {"database_id": database.id})

    assert result.isError is False
    assert json.loads(result.content[0].text) == [
        {
            "id": table.id,
            "name": "Orders",
            "order": table.order,
            "database_id": database.id,
            "database_name": "Sales",
        }
    ]


@pytest.fixture
def linked_tables(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    customers = data_fixture.create_database_table(database=database, name="Customers")
    data_fixture.create_text_field(table=customers, name="Name", primary=True)
    orders = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=orders, name="Order", primary=True)
    handler = FieldHandler()
    status = handler.create_field(
        user,
        orders,
        "single_select",
        name="Status",
        select_options=[{"value": "Open", "color": "blue"}],
    )
    link = handler.create_field(
        user, orders, "link_row", name="Customer", link_row_table=customers
    )
    handler.create_field(
        user,
        orders,
        "lookup",
        name="Customer name",
        through_field_id=link.id,
        target_field_name="Name",
    )
    handler.create_field(
        user, orders, "formula", name="Names", formula="lookup('Customer', 'Name')"
    )
    handler.create_field(user, orders, "number", name="Total", number_decimal_places=2)
    return ToolContext(user=user, workspace=workspace), customers, orders, status


@pytest.mark.django_db
def test_get_table_schema_has_kuma_extras_and_the_old_keys(linked_tables):
    ctx, customers, orders, status = linked_tables

    [schema] = get_table_schema(ctx, [orders.id])

    assert (schema["id"], schema["name"]) == (orders.id, "Orders")
    assert schema["database_id"] == orders.database_id
    fields = {field["name"]: field for field in schema["fields"]}
    assert [field["name"] for field in schema["fields"]][0] == "Order"
    assert fields["Order"]["primary"] is True
    assert fields["Status"]["primary"] is False
    option = status.select_options.get()
    assert fields["Status"]["options"] == [
        {"id": option.id, "value": "Open", "color": "blue"}
    ]
    assert fields["Status"]["select_options"] == fields["Status"]["options"]
    assert fields["Customer"]["linked_table"] == customers.id
    assert fields["Customer"]["link_row_table_id"] == customers.id
    assert fields["Customer"]["link_row_table_name"] == "Customers"
    assert fields["Customer name"]["through_field_name"] == "Customer"
    assert fields["Customer name"]["target_field_name"] == "Name"
    assert fields["Customer name"]["through_field"] == fields["Customer"]["id"]
    assert fields["Names"]["formula_type"] == "array"
    assert fields["Names"]["array_formula_type"] == "text"
    assert fields["Total"]["decimal_places"] == 2
    assert fields["Total"]["number_decimal_places"] == 2
    # The old MCP output sent the generated formula of a lookup.
    lookup = orders.field_set.get(name="Customer name").specific
    assert fields["Customer name"]["formula"] == lookup.formula
    assert fields["Customer name"]["formula_type"] == lookup.formula_type


@pytest.mark.django_db
def test_get_table_schema_overview_lists_primary_and_link_fields(linked_tables):
    ctx, customers, orders, _ = linked_tables

    schemas = get_table_schema(ctx, [orders.id, customers.id], full_schema=False)

    assert [schema["id"] for schema in schemas] == [orders.id, customers.id]
    assert [field["name"] for field in schemas[0]["fields"]] == ["Order", "Customer"]


@pytest.mark.django_db
def test_get_table_schema_leaves_out_tables_of_other_workspaces(
    data_fixture, linked_tables
):
    ctx, customers, *_ = linked_tables
    elsewhere = data_fixture.create_database_table(user=ctx.user)

    schemas = get_table_schema(ctx, [elsewhere.id, customers.id, customers.id])

    assert [schema["id"] for schema in schemas] == [customers.id]


@pytest.mark.django_db
def test_read_tools_over_mcp_keep_their_arguments_and_shape(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    primary = data_fixture.create_text_field(table=table, name="Name", primary=True)
    select = data_fixture.create_single_select_field(table=table, name="Status")
    option = data_fixture.create_select_option(field=select, value="Open")

    async def callback(client):
        listed = await client.list_tools()
        schema = await client.call_tool("get_table_schema", {"table_ids": [table.id]})
        return listed, schema

    token = current_key.set(endpoint.key)
    try:

        async def inner():
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await callback(client)

        with transaction.atomic():
            listed, schema = async_to_sync(inner)()
    finally:
        current_key.reset(token)

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools["list_tables"].inputSchema["properties"]) == {
        "database_id",
        "database_name",
        "table_ids",
        "table_names",
    }
    assert set(tools["get_table_schema"].inputSchema["properties"]) == {
        "table_ids",
        "full_schema",
    }
    for name in ("list_tables", "get_table_schema"):
        for kuma_only in ("ask_user", "navigate", "get_tables_schema", "sample"):
            assert kuma_only not in tools[name].description
    [data] = json.loads(schema.content[0].text)
    assert (data["id"], data["name"], data["database_id"]) == (
        table.id,
        "Orders",
        database.id,
    )
    assert data["fields"][0] == {
        "id": primary.id,
        "name": "Name",
        "type": "text",
        "primary": True,
    }
    assert data["fields"][1]["select_options"] == [
        {"id": option.id, "value": "Open", "color": option.color}
    ]
