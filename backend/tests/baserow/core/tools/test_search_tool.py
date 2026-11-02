"""Tests for the workspace search tool shared by MCP and Kuma."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.exceptions import InstanceTypeDoesNotExist, UserNotInWorkspace
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext
from baserow.core.tools.search import search_workspace


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
def customers(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Sales"
    )
    table, _, rows = data_fixture.build_table(
        user=user,
        database=database,
        name="Customers",
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Acme"]],
    )
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)
    SearchHandler.process_search_data_updates(table)
    return ToolContext(user=user, workspace=workspace), table, rows[0]


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_workspace_finds_table(customers):
    ctx, table, _ = customers

    results = search_workspace(ctx, "Customers")["results"]

    assert [(r["type"], r["id"], r["title"]) for r in results] == [
        ("database_table", table.id, "Customers")
    ]


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_workspace_finds_row_and_where_it_lives(customers):
    ctx, table, row = customers

    result = search_workspace(ctx, "Acme", types=["database_row"])["results"][0]

    assert result["type"] == "database_row"
    assert result["title"] == "Acme"
    assert result["metadata"]["table_id"] == table.id
    assert result["metadata"]["row_id"] == row.id


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_workspace_filter_finds_results_ranked_after_other_types(data_fixture):
    # Filtering a page after the search would leave this page empty: databases
    # rank ahead of tables and fill it.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace, name="Cust 1")
    database = data_fixture.create_database_application(
        workspace=workspace, name="Cust 2"
    )
    table = data_fixture.create_database_table(database=database, name="Cust table")
    ctx = ToolContext(user=user, workspace=workspace)

    result = search_workspace(ctx, "Cust", types=["database_table"], size=1)

    assert [r["id"] for r in result["results"]] == [table.id]
    assert result["has_more"] is False


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_workspace_pages_through_results(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="x")
    first = data_fixture.create_database_table(database=database, name="Cust 1")
    second = data_fixture.create_database_table(database=database, name="Cust 2")
    ctx = ToolContext(user=user, workspace=workspace)

    page_1 = search_workspace(ctx, "Cust", size=1)
    page_2 = search_workspace(ctx, "Cust", page=2, size=1)

    assert {page_1["results"][0]["id"], page_2["results"][0]["id"]} == {
        first.id,
        second.id,
    }
    assert page_1["has_more"] is True
    assert page_2["has_more"] is False


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_workspace_rejects_unknown_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(InstanceTypeDoesNotExist):
        search_workspace(
            ToolContext(user=user, workspace=workspace), "x", types=["nope"]
        )


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_workspace_stays_inside_the_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other = data_fixture.create_database_application(user=user, name="Cust elsewhere")
    data_fixture.create_database_table(database=other, name="Cust elsewhere")

    result = search_workspace(ToolContext(user=user, workspace=workspace), "Cust")

    assert result == {"results": [], "has_more": False}


@pytest.mark.workspace_search
@pytest.mark.django_db
def test_search_workspace_refuses_user_outside_the_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    with pytest.raises(UserNotInWorkspace):
        search_workspace(ToolContext(user=user, workspace=workspace), "Cust")


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_workspace_over_mcp(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="x")
    table = data_fixture.create_database_table(database=database, name="Customers")
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["search_workspace"]
    )

    result = _call(endpoint, "search_workspace", {"query": "Customers"})

    assert not result.isError
    assert json.loads(result.content[0].text)["results"][0]["id"] == table.id


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_workspace_over_mcp_explains_unknown_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["search_workspace"]
    )

    result = _call(endpoint, "search_workspace", {"query": "x", "types": ["nope"]})

    assert result.isError
    assert result.content[0].text == "'nope' is not a valid type."
