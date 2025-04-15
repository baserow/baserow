import contextvars
import traceback

from django.contrib.auth import get_user_model

from mcp.server.lowlevel.server import Server
from mcp.server.lowlevel.server import lifespan as default_lifespan
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent
from mcp.types import Tool as MCPTool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from baserow.core.mcp.registries import mcp_tool_registry

User = get_user_model()
current_endpoint: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_endpoint"
)


class BaserowMCPServer:
    def __init__(self):
        self._mcp_server = Server(
            name="Baserow MCP",
            instructions="Handles all the actions and tools related to Baserow.",
            lifespan=default_lifespan,
        )

        self._setup_handlers()

    def _setup_handlers(self):
        self._mcp_server.list_tools()(self.list_tools)
        self._mcp_server.call_tool()(self.call_tool)

        self._mcp_server.list_resources()(self.return_empty)
        self._mcp_server.list_prompts()(self.return_empty)
        self._mcp_server.list_resource_templates()(self.return_empty)

    async def return_empty(self):
        return []

    async def get_user(self) -> User:
        endpoint = current_endpoint.get()
        # @TODO implement fetching the user dynamically.
        print(f"@TODO fetch user based on endpoint {endpoint}")
        user = await User.objects.aget(email="bram@baserow.io")
        return user

    async def call_tool(self, name: str, arguments):
        user = await self.get_user()
        tool, params = mcp_tool_registry.match_by_name(name)
        if not tool or not params:
            return [TextContent(type="text", text=f"Tool '{name}' not found.")]
        return await tool.call(user, name, params, arguments)

    async def list_tools(self) -> list[MCPTool]:
        user = await self.get_user()
        return await mcp_tool_registry.list_all_tools(user)

    def sse_app(self) -> Starlette:
        sse_path = "/mcp/{endpoint}/sse"
        messages_path = "/mcp/messages/"
        sse = SseServerTransport(messages_path)

        async def handle_sse(request: Request) -> None:
            # Save the token in the context var
            endpoint = request.path_params["endpoint"]
            endpoint_ctx = current_endpoint.set(endpoint)

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
            except Exception:
                traceback.print_exc()
            finally:
                # Reset the context variable when done
                current_endpoint.reset(endpoint_ctx)

        return Starlette(
            debug=False,
            routes=[
                Route(sse_path, endpoint=handle_sse),
                Mount(messages_path, app=sse.handle_post_message),
            ],
        )


baserow_mcp = BaserowMCPServer()
