from django.db import transaction

import anyio
import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import (
    BaserowMCPServer,
    _is_sse_disconnect_teardown_error,
    current_key,
)
from baserow.core.mcp.sse import DjangoChannelsSseServerTransport


def test_is_sse_disconnect_teardown_error():
    benign = RuntimeError("Response already completed.")
    real = ValueError("boom")

    # Bare and ExceptionGroup-wrapped benign errors are recognised. anyio wraps
    # the child-task error from EventSourceResponse in a group.
    assert _is_sse_disconnect_teardown_error(benign) is True
    assert _is_sse_disconnect_teardown_error(ExceptionGroup("tg", [benign])) is True

    # Real errors are not, whether bare, wrapped, or mixed with a benign one.
    assert _is_sse_disconnect_teardown_error(real) is False
    assert _is_sse_disconnect_teardown_error(ExceptionGroup("tg", [real])) is False
    assert (
        _is_sse_disconnect_teardown_error(ExceptionGroup("tg", [benign, real])) is False
    )


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


def test_malformed_post_message_is_not_relayed_to_the_server():
    """
    Regression for BASEROW-SAAS-BACKEND-12K: a POST whose body fails JSON-RPC
    validation must be answered with 400 and must NOT be relayed into the SSE
    stream. The old code sent the error text back through the channel, where the
    listener re-parsed it as a message, failed again, and pushed a misleading
    exception to the server's read stream (logged as a server error).
    """

    async def inner():
        sse = DjangoChannelsSseServerTransport("/mcp/messages/")
        channel_layer = get_channel_layer()

        sse_scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp/key/sse",
            "headers": [],
            "query_string": b"",
        }

        client_disconnected = anyio.Event()

        async def sse_receive():
            await client_disconnected.wait()
            return {"type": "http.disconnect"}

        async def sse_send(message):
            pass

        def listener_group():
            return next(
                (g for g in channel_layer.groups if g.startswith("mcp_sse_")), None
            )

        with anyio.fail_after(10):
            async with sse.connect_sse(sse_scope, sse_receive, sse_send) as (
                read_stream,
                _write_stream,
            ):
                # Wait until the listener has joined its group and can receive POSTs.
                while listener_group() is None:
                    await anyio.sleep(0.01)
                session_hex = listener_group()[len("mcp_sse_") :]

                # Valid JSON, but not a valid JSON-RPC message (missing fields).
                body = b'{"not": "a valid json-rpc message"}'
                post_scope = {
                    "type": "http",
                    "method": "POST",
                    "path": "/mcp/messages/",
                    "headers": [(b"content-type", b"application/json")],
                    "query_string": f"session_id={session_hex}".encode(),
                }

                async def post_receive():
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }

                status = {}

                async def post_send(message):
                    if message["type"] == "http.response.start":
                        status["code"] = message["status"]

                await sse.handle_post_message(post_scope, post_receive, post_send)

                # The client gets a 400 directly on the POST.
                assert status["code"] == 400

                # Nothing must reach the server's read stream. On the pre-fix code
                # a re-parsed ValidationError arrives here and the MCP server logs
                # it as "Received exception from stream".
                received = None
                with anyio.move_on_after(0.5):
                    received = await read_stream.receive()
                assert received is None, (
                    "a malformed POST must not be forwarded to the MCP server, "
                    f"got {received!r}"
                )

                # Tear the connection down cleanly.
                client_disconnected.set()
                async for _ in read_stream:
                    pass

    async_to_sync(inner)()


@pytest.mark.django_db(transaction=True)
def test_handle_sse_sends_a_single_http_response_start(data_fixture):
    """
    Regression for BASEROW-SAAS-BACKEND-Z4: once the SSE transport has started
    streaming, the route must not return a Response that Starlette sends on top,
    because that emits a second http.response.start and raises a RuntimeError.
    """

    endpoint = data_fixture.create_mcp_endpoint()
    app = BaserowMCPServer().sse_app()
    key_token = current_key.set(endpoint.key)

    response_starts = 0

    async def inner():
        nonlocal response_starts
        client_disconnected = anyio.Event()

        async def receive():
            await client_disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal response_starts
            if message["type"] == "http.response.start":
                response_starts += 1
                # Streaming has begun; disconnect so the transport tears down and
                # the route returns.
                client_disconnected.set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/mcp/{endpoint.key}/sse",
            "headers": [],
            "query_string": b"",
        }

        with anyio.fail_after(10):
            await app(scope, receive, send)

    try:
        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)

    # Exactly one start: the SSE stream's. On the pre-fix code Starlette sends a
    # second one for the returned Response().
    assert response_starts == 1


@pytest.mark.django_db(transaction=True)
def test_handle_sse_still_logs_errors_raised_after_the_response_started(data_fixture):
    """
    A real failure inside the MCP session after streaming has begun must stay
    visible (logged at error level), not be swallowed as a benign disconnect,
    while still never sending a second http.response.start.
    """

    from loguru import logger

    endpoint = data_fixture.create_mcp_endpoint()
    mcp = BaserowMCPServer()
    app = mcp.sse_app()
    key_token = current_key.set(endpoint.key)

    errors = []
    sink_id = logger.add(errors.append, level="ERROR")

    response_starts = 0

    async def inner():
        nonlocal response_starts
        response_started = anyio.Event()

        async def failing_run(*args, **kwargs):
            # Wait until the EventSourceResponse has actually sent
            # http.response.start, then fail. Synchronising on the event instead
            # of a fixed sleep keeps the post-response-start branch deterministic
            # on slow/loaded CI.
            await response_started.wait()
            raise ValueError("boom")

        async def receive():
            # Block until the connect_sse teardown cancels this task. Waiting on a
            # never-set event (rather than sleeping for the fail_after window) keeps
            # the test from racing its own timeout boundary.
            await anyio.Event().wait()
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal response_starts
            if message["type"] == "http.response.start":
                response_starts += 1
                response_started.set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": f"/mcp/{endpoint.key}/sse",
            "headers": [],
            "query_string": b"",
        }

        mcp._mcp_server.run = failing_run
        with anyio.fail_after(10):
            await app(scope, receive, send)

    try:
        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        logger.remove(sink_id)
        current_key.reset(key_token)

    # The failure was surfaced as an error, and the response was not double-sent.
    assert response_starts == 1
    assert any(record.record["level"].name == "ERROR" for record in errors)


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
                assert result.isError is True

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_unknown_tool_name(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("nonexistent_tool", {})
                assert result.content[0].text == "Tool 'nonexistent_tool' not found."
                assert result.isError is True

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)


@pytest.mark.django_db
def test_call_tool_exception_returns_is_error_true(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool(
                    "update_rows", {"table_id": 999999, "rows": []}
                )
                assert result.isError is True
                assert "Error:" in result.content[0].text

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)
