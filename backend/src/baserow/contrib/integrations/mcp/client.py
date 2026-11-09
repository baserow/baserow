import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError

from .http import create_mcp_http_client

CLIENT_INFO = types.Implementation(name="Baserow", version="1")

# Longest text a tool result may add to the conversation.
MAX_RESULT_CHARACTERS = 50_000
# Longest tool description shown to the model.
MAX_DESCRIPTION_CHARACTERS = 2_000
# Matches `MCPServerTool.title`.
MAX_TITLE_CHARACTERS = 255
# Most pages of tools read from one server, so one that always returns a next
# cursor can't keep a request or a reply busy forever.
MAX_TOOL_PAGES = 20
# Longest a whole exchange with a server may take, in seconds: listing tools or
# calling one. Each read already has its own timeout, but a server that keeps
# sending a little at a time would otherwise hold a worker forever.
MCP_REQUEST_DEADLINE = 120


@dataclass(frozen=True)
class MCPServerConnection:
    """Where an MCP server is and how to authenticate, without any model."""

    url: str
    # Holds the credential: kept out of reprs, which error reports and logs print.
    headers: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_integration(cls, integration) -> "MCPServerConnection":
        """
        The connection with the integration's credential. An OAuth token must
        be refreshed first if needed, see `MCPServerHandler.get_connection`.
        """

        from .models import MCPAuthType

        headers = {}
        if integration.auth_type == MCPAuthType.OAUTH:
            if integration.oauth_access_token:
                headers["Authorization"] = f"Bearer {integration.oauth_access_token}"
        elif (
            integration.auth_type == MCPAuthType.HEADER
            and integration.auth_header_name
            and integration.auth_header_value
        ):
            headers[integration.auth_header_name] = integration.auth_header_value
        return cls(url=integration.url, headers=headers)


@dataclass(frozen=True)
class MCPToolDefinition:
    """A tool as the server described it."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any] | None

    @property
    def definition_hash(self) -> str:
        """
        Hashes everything the model sees and the server's hints, so any change
        to how the tool is described is noticed.
        """

        payload = json.dumps(
            {
                "name": self.name,
                "title": self.title,
                "description": self.description,
                "input_schema": self.input_schema,
                "annotations": self.annotations,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def from_mcp(cls, tool: types.Tool) -> "MCPToolDefinition":
        annotations = (
            tool.annotations.model_dump(exclude_none=True) if tool.annotations else None
        )
        title = (
            tool.title or (tool.annotations.title if tool.annotations else None) or ""
        )
        return cls(
            name=tool.name,
            # Cut to what is stored, so a definition hashed again from the
            # stored tool, as on import, matches the server's.
            title=title[:MAX_TITLE_CHARACTERS],
            description=tool.description or "",
            input_schema=tool.inputSchema or {"type": "object"},
            annotations=annotations or None,
        )


@asynccontextmanager
async def open_session(connection: MCPServerConnection) -> AsyncIterator[ClientSession]:
    """
    Connect and initialize a session. The server can't ask Baserow to sample a
    model, elicit input or list roots: no handlers are registered for them.

    :param connection: The server to connect to.
    :return: The initialized session.
    """

    async with create_mcp_http_client(connection.headers) as http_client:
        async with streamable_http_client(connection.url, http_client=http_client) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write, client_info=CLIENT_INFO) as session:
                await session.initialize()
                yield session


async def list_tools(session: ClientSession) -> list[MCPToolDefinition]:
    """
    List every tool, following pagination.

    :param session: An initialized session.
    :raises ValueError: When the server lists more than ``MAX_TOOL_PAGES``.
    :return: The tools in the order the server lists them.
    """

    tools: list[MCPToolDefinition] = []
    cursor = None
    for _ in range(MAX_TOOL_PAGES):
        page = await session.list_tools(cursor=cursor)
        tools.extend(MCPToolDefinition.from_mcp(tool) for tool in page.tools)
        cursor = page.nextCursor
        if not cursor:
            return tools
    raise ValueError(f"The MCP server lists more than {MAX_TOOL_PAGES} pages.")


async def fetch_tools(connection: MCPServerConnection) -> list[MCPToolDefinition]:
    """:raises TimeoutError: When it takes longer than the deadline."""

    async with asyncio.timeout(MCP_REQUEST_DEADLINE):
        async with open_session(connection) as session:
            return await list_tools(session)


def refused_credential(exc: BaseException) -> bool:
    """Whether the server answered 401 or 403 somewhere in the failure."""

    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) in (401, 403):
        return True
    nested = list(getattr(exc, "exceptions", [])) + [exc.__cause__]
    return any(refused_credential(inner) for inner in nested if inner)


def protocol_error(exc: BaseException) -> McpError | None:
    """
    The error the server answered with somewhere in the failure, such as invalid
    arguments, as opposed to the server not answering.
    """

    if isinstance(exc, McpError):
        return exc
    nested = list(getattr(exc, "exceptions", [])) + [exc.__cause__]
    for inner in nested:
        if inner and (found := protocol_error(inner)):
            return found
    return None


def result_to_text(result: types.CallToolResult) -> str:
    """
    Turn a tool result into text for the model. Images, audio and embedded
    binary resources are named but not forwarded.

    :param result: The server's result.
    :return: The text, truncated to ``MAX_RESULT_CHARACTERS``.
    """

    parts: list[str] = []
    for item in result.content:
        if isinstance(item, types.TextContent):
            parts.append(item.text)
        elif isinstance(item, types.EmbeddedResource) and isinstance(
            item.resource, types.TextResourceContents
        ):
            parts.append(item.resource.text)
        elif isinstance(item, types.ResourceLink):
            parts.append(f"[Resource: {item.name} {item.uri}]")
        else:
            parts.append(f"[{item.type} content not shown]")
    if not parts and result.structuredContent is not None:
        parts.append(json.dumps(result.structuredContent))
    text = "\n".join(parts)
    if len(text) > MAX_RESULT_CHARACTERS:
        text = text[:MAX_RESULT_CHARACTERS] + "\n[Result truncated.]"
    return text
