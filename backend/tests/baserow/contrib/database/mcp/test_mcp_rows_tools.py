import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.django_db
def test_list_rows_list_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table(database=database)
    table_3 = data_fixture.create_database_table()

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.list_tools()
                tool_names = [tool.name for tool in result.tools]
                assert f"list_table_rows" in tool_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    row = model.objects.create(name="Row 1")

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"list_table_rows", {"table_id": table.id}
                )
                json_result = json.loads(result.content[0].text)
                assert json_result == {
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {"id": 1, "order": "1.00000000000000000000", "Name": "Row 1"}
                    ],
                }

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_table_different_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    table = data_fixture.create_database_table(user=endpoint.user)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"list_table_rows", {"table_id": table.id}
                )
                assert result.content[0].text == "Table not in endpoint workspace."

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_with_search_query(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Car")
    model.objects.create(name="Boat")

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"list_table_rows", {"table_id": table.id, "search": "boat"}
                )
                json_result = json.loads(result.content[0].text)
                assert json_result == {
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {"id": 2, "order": "1.00000000000000000000", "Name": "Boat"}
                    ],
                }

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_list_rows_with_page_and_size(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Car")
    model.objects.create(name="Boat")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"list_table_rows", {"table_id": table.id, "page": 2, "size": 1}
                )
                json_result = json.loads(result.content[0].text)
                assert json_result["count"] == 2
                assert json_result["results"] == [
                    {"id": 2, "order": "1.00000000000000000000", "Name": "Boat"}
                ]

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_create_row_list_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.list_tools()
                tool_names = [tool.name for tool in result.tools]
                assert f"create_row_table_{table_1.id}" in tool_names
                assert f"create_row_table_{table_2.id}" not in tool_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_create_row(data_fixture):
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
                    f"create_row_table_{table.id}", {"row": {"Name": "Test"}}
                )
                json_result = json.loads(result.content[0].text)
                assert json_result == {
                    "id": 1,
                    "order": "1.00000000000000000000",
                    "Name": "Test",
                }

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_create_row_table_different_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    table = data_fixture.create_database_table(user=endpoint.user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"create_row_table_{table.id}", {"row": {"Name": "Test"}}
                )
                assert result.content[0].text == "Table not in endpoint workspace."

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_update_row_list_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.list_tools()
                tool_names = [tool.name for tool in result.tools]
                assert f"update_row_table_{table_1.id}" in tool_names
                assert f"update_row_table_{table_2.id}" not in tool_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_update_row(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Car")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"update_row_table_{table.id}", {"id": 1, "row": {"Name": "Test"}}
                )
                json_result = json.loads(result.content[0].text)
                assert json_result == {
                    "id": 1,
                    "order": "1.00000000000000000000",
                    "Name": "Test",
                }

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_update_row_table_different_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    table = data_fixture.create_database_table(user=endpoint.user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    f"update_row_table_{table.id}", {"id": 1, "row": {"Name": "Test"}}
                )
                assert result.content[0].text == "Table not in endpoint workspace."

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_delete_row_list_tools(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table()

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.list_tools()
                tool_names = [tool.name for tool in result.tools]
                assert f"delete_table_row" in tool_names

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_row(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)
    model.objects.create(name="Car")

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_table_row",
                    {
                        "table_id": table.id,
                        "id": 1,
                    },
                )
                assert result.content[0].text == "successfully deleted"

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_row_not_existing_row(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="Name", table=table, primary=True)
    model = table.get_model(attribute_names=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_table_row",
                    {
                        "table_id": table.id,
                        "id": 1,
                    },
                )
                assert "ERROR_ROW_DOES_NOT_EXIST" in result.content[0].text

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_delete_row_table_different_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    table = data_fixture.create_database_table(user=endpoint.user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "delete_table_row",
                    {
                        "table_id": table.id,
                        "id": 1,
                    },
                )
                assert result.content[0].text == "Table not in endpoint workspace."

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)
