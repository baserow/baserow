"""Tests for static MCP table, database, and field tools."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key

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
    "create_database",
    "create_table",
    "update_table",
    "delete_table",
    "create_fields",
    "update_fields",
    "delete_fields",
}

ALL_TOOL_NAMES = ENABLED_TOOL_NAMES | DISABLED_TOOL_NAMES


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
def test_call_tool_create_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("create_database", {"name": "My DB"})
                data = json.loads(result.content[0].text)
                assert data["name"] == "My DB"
                assert isinstance(data["id"], int)

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
                    },
                    {
                        "id": table_2.id,
                        "name": table_2.name,
                        "order": table_2.order,
                        "database_id": table_2.database_id,
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
def test_call_tool_create_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "create_table",
                    {
                        "database_id": db.id,
                        "name": "Orders",
                        "fields": [{"name": "Customer", "type": "text"}],
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["name"] == "Orders"
                assert data["database_id"] == db.id
                assert isinstance(data["id"], int)
                field_names = [f["name"] for f in data["fields"]]
                assert "Customer" in field_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_call_tool_create_fields(data_fixture):
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
                result = await client.call_tool(
                    "create_fields",
                    {
                        "table_id": table.id,
                        "fields": [{"name": "Status", "type": "text"}],
                    },
                )
                data = json.loads(result.content[0].text)
                assert len(data) == 1
                assert data[0]["name"] == "Status"
                assert data[0]["type"] == "text"

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_update_fields(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    field = data_fixture.create_text_field(name="Old Name", table=table)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "update_fields",
                    {"fields": [{"id": field.id, "name": "New Name"}]},
                )
                data = json.loads(result.content[0].text)
                assert len(data) == 1
                assert data[0]["name"] == "New Name"

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_fields(data_fixture):
    from baserow.contrib.database.fields.models import Field

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    db = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=db)
    field = data_fixture.create_text_field(name="ToDelete", table=table)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_fields", {"field_ids": [field.id]}
                )
                assert result.content[0].text == "Fields successfully deleted."

        with transaction.atomic():
            async_to_sync(inner)()

        assert not Field.objects.filter(id=field.id, trashed=False).exists()
    finally:
        current_key.reset(key_token)
