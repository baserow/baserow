from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.django_db
def test_create_server():
    async def inner():
        mcp = BaserowMCPServer()
        assert mcp._mcp_server.name == "Baserow MCP"
        assert "Baserow" in mcp._mcp_server.instructions

    with transaction.atomic():
        async_to_sync(inner)()


@pytest.mark.django_db
def test_get_endpoint_invalid_key(data_fixture):
    mcp = BaserowMCPServer()

    key_token = current_key.set("test-key")

    try:

        async def inner():
            endpoint = await mcp.get_endpoint()
            assert endpoint is None

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_get_endpoint_user_not_part_of_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                endpoint = await mcp.get_endpoint()
            assert endpoint is None

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_get_valid_endpoint(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                endpoint = await mcp.get_endpoint()
                assert endpoint.id == endpoint.id

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_list_tools_without_endpoint_key(data_fixture):
    mcp = BaserowMCPServer()
    key_token = current_key.set("test-key")

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                # Because the endpoint key is invalid, it should not respond with any
                # tools.
                tools = await client.list_tools()
                assert len(tools.tools) == 0

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_list_tools_with_valid_endpoint_key(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    mcp = BaserowMCPServer()
    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                # Because the endpoint key is invalid, it should not respond with any
                # tools.
                tools = await client.list_tools()
                assert len(tools.tools) > 0

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_without_endpoint_key(data_fixture):
    mcp = BaserowMCPServer()

    key_token = current_key.set("test-key")

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                # Because the endpoint key is invalid, it should not respond with any
                # tools.
                result = await client.call_tool("list_tables", {})
                assert result.content[0].text == "Endpoint not found."

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)
