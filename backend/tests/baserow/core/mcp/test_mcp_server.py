import pytest
from asgiref.sync import sync_to_async
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.asyncio
async def test_create_server():
    mcp = BaserowMCPServer()
    assert mcp._mcp_server.name == "Baserow MCP"
    assert "Baserow" in mcp._mcp_server.instructions


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_endpoint_invalid_key(data_fixture):
    mcp = BaserowMCPServer()

    key_token = current_key.set("test-key")

    try:
        endpoint = await mcp.get_endpoint()
        assert endpoint is None
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_endpoint_user_not_part_of_workspace(data_fixture):
    def setup():
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace()
        endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
        return endpoint

    endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:
        endpoint = await mcp.get_endpoint()
        assert endpoint is None
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_valid_endpoint(data_fixture):
    def setup():
        user = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user)
        endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
        return endpoint

    setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        endpoint = await mcp.get_endpoint()
        assert endpoint.id == setup_endpoint.id
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_tools_without_endpoint_key(data_fixture):
    mcp = BaserowMCPServer()

    key_token = current_key.set("test-key")

    try:
        async with client_session(mcp._mcp_server) as client:
            # Because the endpoint key is invalid, it should not respond with any tools.
            tools = await client.list_tools()
            assert len(tools.tools) == 0
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_list_tools_with_valid_endpoint_key(data_fixture):
    def setup():
        endpoint = data_fixture.create_mcp_endpoint()
        return endpoint

    setup_endpoint = await sync_to_async(setup)()

    mcp = BaserowMCPServer()

    key_token = current_key.set(setup_endpoint.key)

    try:
        async with client_session(mcp._mcp_server) as client:
            # Because the endpoint key is invalid, it should not respond with any tools.
            tools = await client.list_tools()
            assert len(tools.tools) > 0
    finally:
        current_key.reset(key_token)


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_call_tool_without_endpoint_key(data_fixture):
    mcp = BaserowMCPServer()

    key_token = current_key.set("test-key")

    try:
        async with client_session(mcp._mcp_server) as client:
            # Because the endpoint key is invalid, it should not respond with any tools.
            result = await client.call_tool("list_tables", {})
            assert result.content[0].text == "Endpoint not found."
    finally:
        current_key.reset(key_token)
