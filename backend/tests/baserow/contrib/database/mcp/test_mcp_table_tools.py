"""Tests for static MCP table and database tools."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.registries import mcp_tool_registry

ENABLED_TOOL_NAMES = {
    "list_databases",
    "list_tables",
    "get_table_schema",
    "list_table_rows",
    "create_rows",
    "update_rows",
    "delete_rows",
}

DISABLED_TOOL_NAMES = {
    "update_table",
    "delete_table",
}

ALL_TOOL_NAMES = ENABLED_TOOL_NAMES | DISABLED_TOOL_NAMES


@pytest.fixture
def enable_all_tools(monkeypatch):
    """Disabled tools can't be called, so turn them on to test their logic."""

    for name in DISABLED_TOOL_NAMES:
        monkeypatch.setattr(mcp_tool_registry.get(name), "enabled", True)
    # An endpoint without an allow-list only gets the legacy default tools.
    monkeypatch.setattr(
        "baserow.core.mcp.registries.LEGACY_DEFAULT_TOOLS",
        [*LEGACY_DEFAULT_TOOLS, *DISABLED_TOOL_NAMES],
    )


@pytest.mark.django_db
def test_list_tools_returns_only_enabled_tools(data_fixture):
    """tools/list must return only enabled tools, hiding disabled ones."""
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    for _ in range(5):
        data_fixture.create_database_table(database=database)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.list_tools()
                names = {t.name for t in result.tools}
                assert names == ENABLED_TOOL_NAMES
                assert not names & DISABLED_TOOL_NAMES

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_databases(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db1 = data_fixture.create_database_application(workspace=workspace)
    db2 = data_fixture.create_database_application(workspace=workspace)
    # Different workspace — must not appear.
    data_fixture.create_database_application()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("list_databases", {})
                data = json.loads(result.content[0].text)
                ids = [d["id"] for d in data]
                assert db1.id in ids
                assert db2.id in ids
                assert len(ids) == 2

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_tables(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    database_3 = data_fixture.create_database_application()

    table_1 = data_fixture.create_database_table(database=database_1)
    table_2 = data_fixture.create_database_table(database=database_2)
    # Different workspace — must not appear.
    data_fixture.create_database_table(database=database_3)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("list_tables", {})
                data = json.loads(result.content[0].text)
                assert data == [
                    {
                        "id": table_1.id,
                        "name": table_1.name,
                        "order": table_1.order,
                        "database_id": table_1.database_id,
                        "database_name": table_1.database.name,
                    },
                    {
                        "id": table_2.id,
                        "name": table_2.name,
                        "order": table_2.order,
                        "database_id": table_2.database_id,
                        "database_name": table_2.database.name,
                    },
                ]

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_tables_filtered_by_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db1 = data_fixture.create_database_application(workspace=workspace)
    db2 = data_fixture.create_database_application(workspace=workspace)
    t1 = data_fixture.create_database_table(database=db1)
    data_fixture.create_database_table(database=db2)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("list_tables", {"database_id": db1.id})
                data = json.loads(result.content[0].text)
                assert len(data) == 1
                assert data[0]["id"] == t1.id

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
@pytest.mark.usefixtures("enable_all_tools")
def test_call_tool_update_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db, name="Old Name")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "update_table", {"table_id": table.id, "name": "New Name"}
                )
                data = json.loads(result.content[0].text)
                assert data["name"] == "New Name"
                assert data["id"] == table.id

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
@pytest.mark.usefixtures("enable_all_tools")
def test_call_tool_delete_table(data_fixture):
    from baserow.contrib.database.table.models import Table

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("delete_table", {"table_id": table.id})
                assert result.content[0].text == "Table successfully deleted."

        with transaction.atomic():
            async_to_sync(inner)()

        assert not Table.objects.filter(id=table.id, trashed=False).exists()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_get_table_schema(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    data_fixture.create_text_field(name="Title", table=table, primary=True)
    data_fixture.create_number_field(name="Score", table=table)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "get_table_schema", {"table_ids": [table.id]}
                )
                schemas = json.loads(result.content[0].text)
                assert len(schemas) == 1
                schema = schemas[0]
                assert schema["id"] == table.id
                assert schema["name"] == table.name
                field_names = [f["name"] for f in schema["fields"]]
                assert "Title" in field_names
                assert "Score" in field_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_get_table_schema_excludes_other_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    other_table = data_fixture.create_database_table()  # different workspace

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "get_table_schema", {"table_ids": [other_table.id]}
                )
                schemas = json.loads(result.content[0].text)
                assert schemas == []

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


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


@pytest.mark.django_db
def test_legacy_table_tools_ignore_unknown_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    listed = _call(endpoint, "list_tables", {"bogus": 1})
    schema = _call(endpoint, "get_table_schema", {"table_ids": [table.id], "bogus": 1})

    assert listed.isError is False
    assert [t["id"] for t in json.loads(listed.content[0].text)] == [table.id]
    assert schema.isError is False
    assert [t["id"] for t in json.loads(schema.content[0].text)] == [table.id]


@pytest.mark.django_db
def test_new_table_tools_still_reject_unknown_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)

    result = _call(
        endpoint,
        "create_tables",
        {"database_id": database.id, "tables": [], "bogus": 1},
    )

    assert result.isError is True
    assert "bogus: Extra inputs are not permitted" in result.content[0].text
