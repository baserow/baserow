import asyncio
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger
from pydantic_ai import RunContext, ToolReturn
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_core import SchemaValidator, core_schema

from baserow.core.tools.errors import ToolErrorCode

from .client import (
    MAX_DESCRIPTION_CHARACTERS,
    MCP_REQUEST_DEADLINE,
    MCPServerConnection,
    list_tools,
    open_session,
    result_to_text,
)

# Providers accept tool names matching ^[a-zA-Z0-9_-]{1,64}$.
MODEL_TOOL_NAME_MAX_LENGTH = 64
_INVALID_NAME_CHARACTERS = re.compile(r"[^a-zA-Z0-9_-]")

# The server validates arguments against its own schema; Baserow only checks
# they are an object.
_ARGUMENTS_VALIDATOR = SchemaValidator(
    core_schema.dict_schema(core_schema.str_schema(), core_schema.any_schema())
)

UNREACHABLE_MESSAGE = "The MCP server could not be reached. Try again later."
CHANGED_MESSAGE = (
    "The MCP server changed this tool since it was turned on. An editor of the "
    "Agent has to review it before it can be used."
)


@dataclass(frozen=True)
class MCPToolSnapshot:
    """A tool an editor turned on, as it was described when they did."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    definition_hash: str
    changes_data: bool


@dataclass(frozen=True)
class MCPServerSnapshot:
    """
    Everything a reply needs to call one server's tools, read before the reply
    starts so the event loop never touches the database.
    """

    integration_id: int
    name: str
    connection: MCPServerConnection
    tools: tuple[MCPToolSnapshot, ...]

    @classmethod
    def from_integration(cls, integration, tools) -> "MCPServerSnapshot":
        return cls(
            integration_id=integration.id,
            name=integration.name,
            connection=MCPServerConnection.from_integration(integration),
            tools=tuple(
                MCPToolSnapshot(
                    name=tool.name,
                    title=tool.title,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    definition_hash=tool.definition_hash,
                    changes_data=tool.changes_data,
                )
                for tool in tools
            ),
        )

    def model_tool_names(self) -> dict[str, MCPToolSnapshot]:
        """
        Name each tool for the model, unique across servers and the built-in
        tools: ``mcp<integration id>_<tool name>``, invalid characters replaced
        and cut to the providers' limit. A tool whose name would clash after
        that is left out.

        :return: The tools by the name the model calls them with.
        """

        prefix = f"mcp{self.integration_id}_"
        names: dict[str, MCPToolSnapshot] = {}
        for tool in self.tools:
            name = (prefix + _INVALID_NAME_CHARACTERS.sub("_", tool.name))[
                :MODEL_TOOL_NAME_MAX_LENGTH
            ]
            if name in names:
                logger.info(
                    "MCP server {} tool name clash, tool left out",
                    self.integration_id,
                )
                continue
            names[name] = tool
        return names


def _error(message: str, code: ToolErrorCode) -> ToolReturn:
    return ToolReturn(return_value={"error": message}, metadata={"error_code": code})


class MCPServerToolset(AbstractToolset[Any]):
    """
    The turned-on tools of one MCP server, as pydantic-ai tools.

    The model sees the definitions stored when an editor reviewed them, so a
    reply that calls none of them never contacts the server. The first call of
    a reply lists the server's tools and refuses any whose definition changed
    since the review. Each call opens its own session: tool calls run in their
    own tasks, and a session must be closed by the task that opened it.
    """

    def __init__(self, server: MCPServerSnapshot):
        self._server = server
        self._tools = server.model_tool_names()
        self._verified: dict[str, bool] | None = None
        self._verify_lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return f"mcp_server_{self._server.integration_id}"

    @property
    def label(self) -> str:
        return f"MCP server {self._server.name!r}"

    def get_tool_snapshot(self, model_name: str) -> MCPToolSnapshot | None:
        return self._tools.get(model_name)

    def get_step_input(self, model_name: str) -> dict[str, str]:
        """
        Name the server and tool in the reply's steps. Both were reviewed by an
        editor; the call's arguments may hold anything and are never shown.
        """

        tool = self._tools[model_name]
        return {"server": self._server.name, "tool": tool.title or tool.name}

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        tools = {}
        for model_name, tool in self._tools.items():
            description = tool.description[:MAX_DESCRIPTION_CHARACTERS]
            tools[model_name] = ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=model_name,
                    description=(
                        f"[{self._server.name} (MCP server)] "
                        f"{tool.title or tool.name}. {description}"
                    ).strip(),
                    parameters_json_schema=tool.input_schema or {"type": "object"},
                    sequential=tool.changes_data,
                ),
                max_retries=ctx.max_retries,
                args_validator=_ARGUMENTS_VALIDATOR,
            )
        return tools

    async def _verify(self, session) -> dict[str, bool]:
        """
        Compare the server's current definitions with the reviewed ones, once
        per reply.

        :param session: An open session to the server.
        :return: Whether each reviewed tool still has its reviewed definition.
        """

        async with self._verify_lock:
            if self._verified is None:
                current = {
                    tool.name: tool.definition_hash
                    for tool in await list_tools(session)
                }
                self._verified = {
                    tool.name: current.get(tool.name) == tool.definition_hash
                    for tool in self._tools.values()
                }
            return self._verified

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> ToolReturn:
        snapshot = self._tools[name]
        try:
            async with asyncio.timeout(MCP_REQUEST_DEADLINE):
                async with open_session(self._server.connection) as session:
                    verified = await self._verify(session)
                    if not verified.get(snapshot.name):
                        return _error(CHANGED_MESSAGE, ToolErrorCode.PERMISSION_DENIED)
                    result = await session.call_tool(snapshot.name, tool_args)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.info(
                "MCP server {} tool call failed ({})",
                self._server.integration_id,
                type(exc).__name__,
            )
            return _error(UNREACHABLE_MESSAGE, ToolErrorCode.FAILED)

        text = result_to_text(result)
        if result.isError:
            return _error(text or "The tool failed.", ToolErrorCode.FAILED)
        return ToolReturn(return_value=text, metadata={"server": self._server.name})
