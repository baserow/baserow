import contextvars
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from loguru import logger

from baserow.core.mcp.sse import DjangoChannelsSseServerTransport

if TYPE_CHECKING:
    from mcp.types import Tool
    from starlette.applications import Starlette

current_key: contextvars.ContextVar[str] = contextvars.ContextVar("current_key")
# Set by `/mcp` once the bearer is resolved. It takes precedence over `current_key`,
# so endpoints of OAuth grants, whose key is refused, still resolve for their tokens.
current_endpoint_id: contextvars.ContextVar[int] = contextvars.ContextVar(
    "current_endpoint_id"
)


def _is_sse_disconnect_teardown_error(exc: BaseException) -> bool:
    """
    True if `exc` is only the benign "response already completed" RuntimeError
    raised while the SSE stream tears down on client disconnect. anyio wraps
    child-task errors in an ExceptionGroup, so unwrap before checking.
    """

    if isinstance(exc, BaseExceptionGroup):
        return all(_is_sse_disconnect_teardown_error(e) for e in exc.exceptions)
    return isinstance(exc, RuntimeError) and "already completed" in str(exc)


class BaserowMCPServer:
    """
    This class is inspired by FastMCP
    (https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/fastmcp/server.py)
    but modified to work better in combination with Django Rest Framework that Baserow
    uses.

    The MCP server can be tested with tools like:

    SERVER_PORT=3001 npx @modelcontextprotocol/inspector
    npx @wong2/mcp-cli --sse URL
    """

    def __init__(self):
        from mcp.server.lowlevel.server import Server
        from mcp.server.lowlevel.server import lifespan as default_lifespan

        self._mcp_server = Server(
            name="Baserow MCP",
            instructions="Handles all the actions, operations, mutations, and tools "
            "related to Baserow.",
            lifespan=default_lifespan,
        )

        self._setup_handlers()

    def _setup_handlers(self):
        self._mcp_server.list_tools()(self.list_tools)
        # Each tool validates its own arguments with its pydantic input_schema, so
        # invalid calls reach call_tool and are captured as failed.
        self._mcp_server.call_tool(validate_input=False)(self.call_tool)

        # Return an empty list because there are no resources, prompts, and
        # resource_templates in Baserow.
        self._mcp_server.list_resources()(self.return_empty)
        self._mcp_server.list_prompts()(self.return_empty)
        self._mcp_server.list_resource_templates()(self.return_empty)

    async def return_empty(self) -> list:
        """
        Placeholder so that the server always responds with an empty list when certain
        resources are requested.
        """

        return []

    async def get_endpoint(self):
        from baserow.core.mcp.models import MCPEndpoint
        from baserow.core.subjects import UserSubjectType

        endpoint_id = current_endpoint_id.get(None)
        if endpoint_id is not None:
            lookup = {"id": endpoint_id}
        else:
            # The key of an OAuth grant's endpoint is never a credential.
            lookup = {"key": current_key.get(), "oauth_client_id__isnull": True}
        try:
            endpoint = await MCPEndpoint.objects.select_related(
                "user", "user__profile", "workspace"
            ).aget(**lookup)
            # This call checks if the user is active, account is not deleted, and if it
            # belongs in the workspace. It's important to check this everytime an
            # operation is done because the permissions could have changed.
            check_method = UserSubjectType().is_in_workspace
            valid = await sync_to_async(check_method)(endpoint.user, endpoint.workspace)
            if not valid:
                return None
            return endpoint
        except MCPEndpoint.DoesNotExist:
            return None

    async def call_tool(self, name: str, arguments):
        from mcp.types import CallToolResult, TextContent

        from baserow.core.mcp.registries import mcp_tool_registry

        endpoint = await self.get_endpoint()
        if not endpoint:
            return CallToolResult(
                content=[TextContent(type="text", text="Endpoint not found.")],
                isError=True,
            )
        tool = mcp_tool_registry.get_allowed_tool(endpoint, name)
        if not tool:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Tool '{name}' not found.")],
                isError=True,
            )
        try:
            result = await tool.call(endpoint, arguments)
        except Exception as e:
            logger.exception("Unhandled exception in MCP tool '{}'", name)
            self.capture_event(
                endpoint, "mcp_tool_called", {"tool": name, "success": False}
            )
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {e}")],
                isError=True,
            )
        self.capture_event(endpoint, "mcp_tool_called", {"tool": name, "success": True})
        return result

    def capture_event(self, endpoint, event: str, properties: dict):
        """
        Sends a PostHog event for the endpoint's user. Tool arguments and results
        must never be passed in because they can hold row data.
        """

        from baserow.core.posthog import capture_user_event

        capture_user_event(
            endpoint.user,
            event,
            {"endpoint_id": endpoint.id, **properties},
            workspace=endpoint.workspace,
        )

    async def list_tools(self) -> list["Tool"]:
        from baserow.core.mcp.registries import mcp_tool_registry

        endpoint = await self.get_endpoint()
        if not endpoint:
            # It's only possible to respond with a list of `MCPTool` objects. If the
            # user isn't active anymore, then we can respond with an empty list,
            # insinuating that nothing is possible anymore.
            return []
        return await mcp_tool_registry.list_all_tools(endpoint)

    async def _handle_streamable_http(self, scope, receive, send) -> None:
        """
        Serves one Streamable HTTP request with its own stateless transport, like
        `StreamableHTTPSessionManager._handle_stateless_request`. The session manager
        itself needs an ASGI lifespan, which Channels' ProtocolTypeRouter does not
        forward.
        """

        import anyio
        from mcp.server.streamable_http import StreamableHTTPServerTransport

        transport = StreamableHTTPServerTransport(
            mcp_session_id=None, is_json_response_enabled=True
        )

        async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
            async with transport.connect() as (read_stream, write_stream):
                task_status.started()
                try:
                    await self._mcp_server.run(
                        read_stream,
                        write_stream,
                        self._mcp_server.create_initialization_options(),
                        stateless=True,
                    )
                except Exception:
                    logger.exception("Stateless MCP request crashed")

        async with anyio.create_task_group() as tg:
            await tg.start(run_server)
            try:
                await transport.handle_request(scope, receive, send)
            finally:
                await transport.terminate()

    def sse_app(self) -> "Starlette":
        """
        Returns an ASGI application that can handle MCP SSE connections.

        return: Starlette: The ASGI application for handling MCP SSE connections.
        """

        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response
        from starlette.routing import Mount, Route

        sse_path = "/mcp/{key}/sse"
        messages_path = "/mcp/messages/"
        sse = DjangoChannelsSseServerTransport(messages_path)

        class _AlreadyStreamedResponse(Response):
            """
            A response that sends nothing, because the SSE transport already sent one.

            Returning a normal Response here makes Starlette send a second
            http.response.start, which uvicorn rejects (Sentry BASEROW-SAAS-BACKEND-Z4).
            """

            async def __call__(self, scope, receive, send) -> None:
                return

        async def handle_sse(request: Request) -> Response:
            key = request.path_params["key"]
            key_ctx = current_key.set(key)

            endpoint = await self.get_endpoint()
            if not endpoint:
                # If there is no endpoint, then there is no need to start a
                # connection. It's valid to immediately respond with a 401 error.
                current_key.reset(key_ctx)
                return Response("Endpoint not found.", status_code=401)

            self.capture_event(endpoint, "mcp_connected", {})

            # connect_sse sends the response itself via the send callable. Wrap it to
            # track that, so we can return a no-op instead of one Starlette would send
            # on top.
            response_started = False
            send = request._send

            async def tracking_send(message):
                nonlocal response_started
                if message["type"] == "http.response.start":
                    response_started = True
                await send(message)

            try:
                async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    tracking_send,
                ) as streams:
                    await self._mcp_server.run(
                        streams[0],
                        streams[1],
                        self._mcp_server.create_initialization_options(),
                    )
                return _AlreadyStreamedResponse() if response_started else Response()
            except Exception as exc:
                if not response_started:
                    logger.exception("Error while handling SSE connection")
                    return Response("MCP server error", status_code=500)
                # Headers are already out, so we can never send an error status
                # without re-triggering Z4. Still surface real failures: only the
                # known teardown race after a client disconnect is benign noise.
                if _is_sse_disconnect_teardown_error(exc):
                    logger.debug("SSE connection closed after the response started.")
                else:
                    logger.exception("Error after the SSE response had started")
                return _AlreadyStreamedResponse()
            finally:
                # Reset the context variable when done
                current_key.reset(key_ctx)

        server = self

        class _StreamableHTTPApp:
            """
            Stateless Streamable HTTP on `/mcp`, authenticated with an OAuth access
            token or an endpoint key as bearer. A class so Starlette's `Route` treats
            it as a raw ASGI app instead of a `func(request)` endpoint.
            """

            async def __call__(self, scope, receive, send) -> None:
                from baserow.core.mcp.auth import (
                    INSUFFICIENT_SCOPE,
                    INVALID_TOKEN,
                    resolve_bearer,
                    www_authenticate,
                )

                request = Request(scope, receive)
                authorization = request.headers.get("authorization", "")
                scheme, _, value = authorization.partition(" ")
                value = value.strip()
                endpoint, error = None, None
                if scheme.lower() == "bearer" and value:
                    endpoint, error = await resolve_bearer(value)

                id_ctx = current_endpoint_id.set(endpoint.id if endpoint else None)
                try:
                    if endpoint is not None and await server.get_endpoint() is None:
                        endpoint, error = None, INVALID_TOKEN
                    if endpoint is None:
                        status_code = 403 if error == INSUFFICIENT_SCOPE else 401
                        response = JSONResponse(
                            {"error": error or INVALID_TOKEN},
                            status_code=status_code,
                            headers={"WWW-Authenticate": www_authenticate(error)},
                        )
                        await response(scope, receive, send)
                        return
                    await server._handle_streamable_http(scope, receive, send)
                finally:
                    current_endpoint_id.reset(id_ctx)

        streamable_http_app = _StreamableHTTPApp()

        # It might seem a bit hacky to use Starlette here instead of the existing
        # Django logic. However, it made more sense to stay as close to the recommended
        # code of the MCP library
        # https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#mounting-to-an-existing-asgi-server
        # for compatibility reasons. If anything changes in the Python SDK, which seems
        # to be active development, then we should remain close in terms of
        # compatibility.
        return Starlette(
            debug=False,
            routes=[
                # Only POST: a stateless server has no stream to offer on GET, and
                # the spec allows answering that with 405.
                Route("/mcp", endpoint=streamable_http_app, methods=["POST"]),
                Route("/mcp/", endpoint=streamable_http_app, methods=["POST"]),
                Route(sse_path, endpoint=handle_sse),
                Mount(messages_path, app=sse.handle_post_message),
            ],
        )


_baserow_mcp = None


def get_baserow_mcp_server() -> BaserowMCPServer:
    global _baserow_mcp
    if _baserow_mcp is None:
        _baserow_mcp = BaserowMCPServer()
    return _baserow_mcp
