import json

import pytest
from asgiref.sync import sync_to_async
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_rows_list_tools(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table_1 = data_fixture.create_database_table(database=database)
        table_2 = data_fixture.create_database_table(database=database)
        table_3 = data_fixture.create_database_table()
        return table_1, table_2, table_3, endpoint

    table_1, table_2, table_3, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.list_tools()
            tool_names = [tool.name for tool in result.tools]
            assert f"list_rows_table_{table_1.id}" in tool_names
            assert f"list_rows_table_{table_2.id}" in tool_names
            assert f"list_rows_table_{table_3.id}" not in tool_names
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_list_rows(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        field = data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        row = model.objects.create(name="Row 1")
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(f"list_rows_table_{table.id}", {})
            json_result = json.loads(result.content[0].text)
            assert json_result == {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {"id": 1, "order": "1.00000000000000000000", "Name": "Row 1"}
                ],
            }
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_list_rows_table_different_workspace(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        table = data_fixture.create_database_table(user=endpoint.user)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(f"list_rows_table_{table.id}", {})
            assert result.content[0].text == "Table not in endpoint workspace."
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_list_rows_with_search_query(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        field = data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        model.objects.create(name="Car")
        model.objects.create(name="Boat")
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                f"list_rows_table_{table.id}", {"search": "boat"}
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
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_list_rows_with_page_and_size(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        field = data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        model.objects.create(name="Car")
        model.objects.create(name="Boat")
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                f"list_rows_table_{table.id}", {"page": 2, "size": 1}
            )
            json_result = json.loads(result.content[0].text)
            assert json_result["count"] == 2
            assert json_result["results"] == [
                {"id": 2, "order": "1.00000000000000000000", "Name": "Boat"}
            ]
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_row_list_tools(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table_1 = data_fixture.create_database_table(database=database)
        table_2 = data_fixture.create_database_table()
        return table_1, table_2, endpoint

    table_1, table_2, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.list_tools()
            tool_names = [tool.name for tool in result.tools]
            assert f"create_row_table_{table_1.id}" in tool_names
            assert f"create_row_table_{table_2.id}" not in tool_names
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_create_row(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
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
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_create_row_table_different_workspace(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        table = data_fixture.create_database_table(user=endpoint.user)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                f"create_row_table_{table.id}", {"row": {"Name": "Test"}}
            )
            assert result.content[0].text == "Table not in endpoint workspace."
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_update_row_list_tools(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table_1 = data_fixture.create_database_table(database=database)
        table_2 = data_fixture.create_database_table()
        return table_1, table_2, endpoint

    table_1, table_2, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.list_tools()
            tool_names = [tool.name for tool in result.tools]
            assert f"update_row_table_{table_1.id}" in tool_names
            assert f"update_row_table_{table_2.id}" not in tool_names
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_update_row(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        model.objects.create(name="Car")
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
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
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_update_row_table_different_workspace(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        table = data_fixture.create_database_table(user=endpoint.user)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                f"update_row_table_{table.id}", {"id": 1, "row": {"Name": "Test"}}
            )
            assert result.content[0].text == "Table not in endpoint workspace."
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_delete_row_list_tools(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table_1 = data_fixture.create_database_table(database=database)
        table_2 = data_fixture.create_database_table()
        return table_1, table_2, endpoint

    table_1, table_2, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.list_tools()
            tool_names = [tool.name for tool in result.tools]
            assert f"delete_row_table_{table_1.id}" in tool_names
            assert f"delete_row_table_{table_2.id}" not in tool_names
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_delete_row(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        model.objects.create(name="Car")
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                f"delete_row_table_{table.id}",
                {
                    "id": 1,
                },
            )
            assert result.content[0].text == "successfully deleted"
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_delete_row_not_existing_row(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        database = data_fixture.create_database_application(
            workspace=endpoint.workspace
        )
        table = data_fixture.create_database_table(database=database)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        model = table.get_model(attribute_names=True)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with (client_session(mcp._mcp_server) as client):
            result = await client.call_tool(
                f"delete_row_table_{table.id}",
                {
                    "id": 1,
                },
            )
            assert "ERROR_ROW_DOES_NOT_EXIST" in result.content[0].text
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_delete_row_table_different_workspace(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        table = data_fixture.create_database_table(user=endpoint.user)
        data_fixture.create_text_field(name="Name", table=table, primary=True)
        return table, endpoint

    table, setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with (client_session(mcp._mcp_server) as client):
            result = await client.call_tool(
                f"delete_row_table_{table.id}",
                {
                    "id": 1,
                },
            )
            assert result.content[0].text == "Table not in endpoint workspace."
    finally:
        current_key.reset(key_token)
