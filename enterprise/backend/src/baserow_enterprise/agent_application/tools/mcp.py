import re
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from pydantic_ai.toolsets.wrapper import WrapperToolset
from typing_extensions import Self

from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentDefinition, AgentTool

# A dead or slow MCP server must not stall the whole run.
MCP_INIT_TIMEOUT_SECONDS = 15
MCP_READ_TIMEOUT_SECONDS = 60


def get_mcp_tool_prefix(tool: "AgentTool") -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (tool.name or "").lower()).strip("_")
    return slug or f"mcp_{tool.id}"


class FailsafeMCPToolset(WrapperToolset):
    """
    Keeps an unreachable MCP server from aborting the run: when connecting
    fails the server simply contributes no tools and a note is added for the
    model.
    """

    def __init__(self, wrapped, server_name: str, deps: "AgentRunDeps"):
        super().__init__(wrapped)
        self._server_name = server_name
        self._deps = deps
        self._connected = False

    async def __aenter__(self) -> Self:
        try:
            await super().__aenter__()
            self._connected = True
        except Exception:
            logger.exception(
                "Failed to connect to the MCP server {}", self._server_name
            )
            self._deps.system_notes.append(
                f"The MCP server '{self._server_name}' could not be reached; "
                "its tools are unavailable in this conversation."
            )
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        if not self._connected:
            return None
        return await super().__aexit__(*args)

    async def get_tools(self, ctx):
        if not self._connected:
            return {}
        try:
            return await super().get_tools(ctx)
        except Exception:
            logger.exception(
                "Failed to list tools of the MCP server {}", self._server_name
            )
            return {}


class McpServerAgentToolType(AgentToolType):
    """
    Connects an external MCP (Model Context Protocol) server to the agent;
    the server's tools become callable in every run. MCP tools are treated as
    writes because nothing guarantees they only read, so they sit behind the
    approval queue unless explicitly disabled.
    """

    type = "mcp"
    is_configurable = True

    def can_enable(self, agent: "AgentDefinition") -> tuple[bool, Optional[str]]:
        return True, None

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        from pydantic_ai.mcp import MCPToolset

        from .gating import wrap_approval_required

        url = (tool.config.get("url") or "").strip()
        if not url:
            return []

        headers = tool.config.get("headers") or None
        if headers is not None and not isinstance(headers, dict):
            headers = None

        server_name = tool.name or url
        prefix = get_mcp_tool_prefix(tool)
        toolset = MCPToolset(
            url,
            id=prefix,
            headers=headers,
            init_timeout=MCP_INIT_TIMEOUT_SECONDS,
            read_timeout=MCP_READ_TIMEOUT_SECONDS,
        )
        # Prefixing the tool names avoids collisions between multiple MCP
        # servers exposing the same tool.
        wrapped = FailsafeMCPToolset(toolset.prefixed(prefix), server_name, deps)

        if tool.config.get("require_approval", True):
            return [wrap_approval_required(wrapped)]
        return [wrapped]
