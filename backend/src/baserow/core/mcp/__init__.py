import contextvars
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from loguru import logger

from baserow.core.mcp.sse import DjangoChannelsSseServerTransport

if TYPE_CHECKING:
    from mcp.types import Tool
    from starlette.applications import Starlette

current_key: contextvars.ContextVar[str] = contextvars.ContextVar("current_key")


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
        self._mcp_server.call_tool()(self.call_tool)

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

        key = current_key.get()
        try:
            endpoint = await MCPEndpoint.objects.select_related(
                "user", "user__profile", "workspace"
            ).aget(key=key)
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
        from mcp.types import TextContent

        from baserow.core.mcp.registries import mcp_tool_registry

        endpoint = await self.get_endpoint()
        if not endpoint:
            return [TextContent(type="text", text=f"Endpoint not found.")]
        tool, params = mcp_tool_registry.match_by_name(name)
        if not tool or params is None:
            return [TextContent(type="text", text=f"Tool '{name}' not found.")]
        return await tool.call(endpoint, name, params, arguments)

    async def list_tools(self) -> list["Tool"]:
        from baserow.core.mcp.registries import mcp_tool_registry

        endpoint = await self.get_endpoint()
        if not endpoint:
            # It's only possible to respond with a list of `MCPTool` objects. If the
            # user isn't active anymore, then we can respond with an empty list,
            # insinuating that nothing is possible anymore.
            return []
        return await mcp_tool_registry.list_all_tools(endpoint)

    def sse_app(self) -> "Starlette":
        """
        Returns an ASGI application that can handle MCP SSE connections.

        return: Starlette: The ASGI application for handling MCP SSE connections.
        """

        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import Response
        from starlette.routing import Mount, Route

        sse_path = "/mcp/{key}/sse"
        messages_path = "/mcp/messages/"
        sse = DjangoChannelsSseServerTransport(messages_path)

        async def handle_sse(request: Request) -> None:
            key = request.path_params["key"]
            key_ctx = current_key.set(key)

            endpoint = await self.get_endpoint()
            if not endpoint:
                # If there is no endpoint, then there is no need to start a
                # connection. It's valid to immediately respond with a 401 error.
                return Response("Endpoint not found.", status_code=401)

            try:
                async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,  # type: ignore[reportPrivateUsage]
                ) as streams:
                    await self._mcp_server.run(
                        streams[0],
                        streams[1],
                        self._mcp_server.create_initialization_options(),
                    )
                return Response()
            except Exception as exc:
                # This is a known issue in FastMCP
                # (https://github.com/jlowin/fastmcp/issues/671) that is not causing any
                # critical issues in practice, but it does cause some noise in the logs.
                if isinstance(
                    exc, RuntimeError
                ) and "after response already completed" in str(exc):
                    return Response(status_code=204)

                logger.exception("Error while handling SSE connection")
                return Response("MCP server error", status_code=500)
            finally:
                # Reset the context variable when done
                current_key.reset(key_ctx)

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
