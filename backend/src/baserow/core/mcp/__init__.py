import contextvars
from contextlib import asynccontextmanager

from mcp.types import Tool as MCPTool
from mcp.server.sse import SseServerTransport
from mcp.server.lowlevel.server import Server as MCPServer
from mcp.types import TextContent
from mcp.server.lowlevel.server import lifespan as default_lifespan

from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.applications import Starlette

from django.conf import settings

# Context variable to store the token
current_token: contextvars.ContextVar[str] = contextvars.ContextVar("current_token")

class BaserowMCPServer:
    def __init__(self):
        self._mcp_server = MCPServer(
            name="Baserow MCP",
            instructions="@TODO",
            lifespan=default_lifespan,
        )

        self._setup_handlers()

    def _setup_handlers(self):
        self._mcp_server.list_tools()(self.list_tools)
        self._mcp_server.call_tool()(self.call_tool)

    async def call_tool(self, name: str, arguments):
        token = current_token.get()
        return [TextContent(type="text", text=f"Tool '{name}' called with token: {token}")]

    async def list_tools(self) -> list[MCPTool]:
        from drf_spectacular import serializers
        from .utils import serializer_to_openapi_inline
        from baserow.contrib.database.api.tables.serializers import TableSerializer
        import json

        print(
            json.dumps(serializer_to_openapi_inline(
                TableSerializer,
                direction='request'
            ), indent=4)
        )



        token = current_token.get()
        print(f"[list_tools] token: {token}")

        return [
            MCPTool(
                name="create_test",
                description=f"This is a test tool for token: {token}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    },
                    "required": ["name"]
                }
            )
        ]

    def sse_app(self) -> Starlette:
        sse_path = "/mcp/{token}/sse"
        messages_path = "/mcp/messages/"
        sse = SseServerTransport(messages_path)

        async def handle_sse(request: Request) -> None:
            # Save the token in the context var
            token = request.path_params["token"]
            token_ctx = current_token.set(token)

            print('@TODO do token authentication')

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
            finally:
                # Reset the context variable when done
                current_token.reset(token_ctx)

        return Starlette(
            debug=settings.DEBUG,
            routes=[
                Route(sse_path, endpoint=handle_sse),
                Mount(messages_path, app=sse.handle_post_message),
            ],
        )



# Create server instance
baserow_mcp = BaserowMCPServer()

# class BaserowFastMCP(FastMCP):
#     async def list_tools(self) -> list[MCPTool]:
#         """List all available tools."""
#         tools = self._tool_manager.list_tools()
#         for t in tools:
#             print(t.parameters)
#         return [
#             MCPTool(
#                 name=info.name,
#                 description=info.description,
#                 inputSchema=info.parameters,
#             )
#             for info in tools
#         ]


# baserow_mcp = BaserowFastMCP(
#     "Baserow MCP",
#     sse_path="/mcp/sse",
#     message_path="/mcp/messages/"
# )
