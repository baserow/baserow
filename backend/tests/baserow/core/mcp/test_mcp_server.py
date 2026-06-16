from django.db import transaction

import anyio
import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.sse import DjangoChannelsSseServerTransport


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


def test_sse_listener_is_closed_when_connection_is_closed():
    async def inner():
        sse = DjangoChannelsSseServerTransport("/mcp/messages/")
        channel_layer = get_channel_layer()

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp/key/sse",
            "headers": [],
            "query_string": b"",
        }

        client_disconnected = anyio.Event()

        async def receive():
            # Block until the test simulates the client closing the connection.
            await client_disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            # We don't care about what is sent back to the client.
            pass

        def listener_group():
            return next(
                (g for g in channel_layer.groups if g.startswith("mcp_sse_")), None
            )

        # If the listener is never cancelled, the context manager below hangs
        # forever waiting for it, so guard the whole scenario with a timeout.
        with anyio.fail_after(10):
            async with sse.connect_sse(scope, receive, send) as (
                read_stream,
                _write_stream,
            ):
                # Wait until the listener has joined the group, meaning it now holds
                # an open client that waits for incoming messages.
                while listener_group() is None:
                    await anyio.sleep(0.01)

                # Simulate the client closing the connection. Draining the read
                # stream lets the SSE response finish and the transport tear down.
                client_disconnected.set()
                async for _ in read_stream:
                    pass

        # Once the connection is closed the listener must have been cancelled and
        # discarded itself from the group. If it were still running, it would keep
        # its blocking client open.
        assert listener_group() is None

    async_to_sync(inner)()


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
