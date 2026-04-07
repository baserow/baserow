"""Tests for static MCP row tools (list_table_rows, create_rows, update_rows, delete_rows)."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.django_db
def test_call_tool_list_rows(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Row 1")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "list_table_rows", {"table_id": table.id}
                )
                data = json.loads(result.content[0].text)
                assert data["count"] == 1
                assert len(data["results"]) == 1
                assert data["results"][0]["Name"] == "Row 1"

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_cross_workspace_returns_error(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    other_table = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "list_table_rows", {"table_id": other_table.id}
                )
                assert "does not exist" in result.content[0].text.lower()

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_with_search(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Car")
    model.objects.create(name="Boat")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "list_table_rows", {"table_id": table.id, "search": "boat"}
                )
                data = json.loads(result.content[0].text)
                assert data["count"] == 1
                assert data["results"][0]["Name"] == "Boat"

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_pagination(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Row A")
    model.objects.create(name="Row B")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                page1 = await client.call_tool(
                    "list_table_rows", {"table_id": table.id, "page": 1, "size": 1}
                )
                page2 = await client.call_tool(
                    "list_table_rows", {"table_id": table.id, "page": 2, "size": 1}
                )
                d1 = json.loads(page1.content[0].text)
                d2 = json.loads(page2.content[0].text)
                assert d1["count"] == 2
                assert len(d1["results"]) == 1
                assert len(d2["results"]) == 1
                assert d1["results"][0]["Name"] != d2["results"][0]["Name"]

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_create_rows(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "create_rows",
                    {
                        "table_id": table.id,
                        "rows": [{"Name": "Alice"}, {"Name": "Bob"}],
                    },
                )
                data = json.loads(result.content[0].text)
                assert len(data) == 2
                names = [r["Name"] for r in data]
                assert "Alice" in names
                assert "Bob" in names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_create_rows_cross_workspace_returns_error(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    other_table = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "create_rows",
                    {"table_id": other_table.id, "rows": [{"Name": "Test"}]},
                )
                assert "does not exist" in result.content[0].text.lower()

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_create_rows_unknown_field_returns_error(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "create_rows",
                    {"table_id": table.id, "rows": [{"NoSuchField": "bad"}]},
                )
                assert "Unknown field name" in result.content[0].text

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_update_rows(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    row = model.objects.create(name="Original")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "update_rows",
                    {
                        "table_id": table.id,
                        "rows": [{"id": row.id, "Name": "Updated"}],
                    },
                )
                data = json.loads(result.content[0].text)
                assert len(data) == 1
                assert data[0]["Name"] == "Updated"
                assert data[0]["id"] == row.id

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_update_rows_cross_workspace_returns_error(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    other_table = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "update_rows",
                    {"table_id": other_table.id, "rows": [{"id": 1, "Name": "Test"}]},
                )
                assert "does not exist" in result.content[0].text.lower()

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_rows(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    row1 = model.objects.create(name="Row 1")
    row2 = model.objects.create(name="Row 2")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_rows",
                    {"table_id": table.id, "row_ids": [row1.id, row2.id]},
                )
                assert result.content[0].text == "Rows successfully deleted."

        with transaction.atomic():
            async_to_sync(inner)()

        assert model.objects.filter(trashed=False).count() == 0
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_rows_cross_workspace_returns_error(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    other_table = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_rows",
                    {"table_id": other_table.id, "row_ids": [1]},
                )
                assert "does not exist" in result.content[0].text.lower()

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)
