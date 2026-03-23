import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

from asgiref.sync import sync_to_async
from pydantic import BaseModel

from baserow.core.mcp.models import MCPEndpoint
from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from mcp import Tool
    from mcp.types import EmbeddedResource, ImageContent, TextContent


class MCPTool(Instance):
    """
    Base class for MCP tools.

    Subclasses must set ``type`` (used as both the registry key and the MCP
    tool name) and define a docstring (used as the MCP tool description).

    Set ``input_schema`` to a pydantic ``BaseModel`` subclass to
    auto-generate the JSON Schema and receive a validated instance in
    ``_sync_call``.

    Set ``enabled = False`` to prevent the tool from being exposed to MCP
    clients. Disabled tools will be re-enabled once users can control tool
    availability through the UI.
    """

    input_schema: type[BaseModel] | None = None
    """Pydantic model for the tool's input. Used to generate the JSON Schema."""

    enabled: bool = True
    """Whether the tool is available to MCP clients."""

    @property
    def name(self) -> str:
        """MCP tool name, derived from ``type``."""
        return self.type

    def get_name(self) -> str:
        return self.type

    async def list(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """
        Return the MCP Tool definition(s) for this tool.

        The default implementation builds a single Tool from ``type``
        (as name), the class docstring (as description) and
        ``input_schema``. Override for custom behaviour.
        """
        from mcp import Tool

        schema = (
            self.input_schema.model_json_schema()
            if self.input_schema
            else {"type": "object", "properties": {}}
        )
        description = self.__class__.__doc__
        if description:
            description = " ".join(description.split())
        return [Tool(name=self.type, description=description, inputSchema=schema)]

    async def call(
        self,
        endpoint: MCPEndpoint,
        call_arguments: Dict[str, Any],
    ) -> Sequence[Union["TextContent", "ImageContent", "EmbeddedResource"]]:
        """
        Execute the tool and return MCP content.

        The default implementation calls ``_sync_call`` inside
        ``sync_to_async``, serialises the result as JSON (or plain text if
        already a string), and wraps exceptions in an error message.

        Override ``_sync_call`` for the common case.  Override ``call``
        directly only when you need full async control.
        """
        from mcp.types import TextContent

        if self.input_schema:
            args = self.input_schema(**call_arguments)
        else:
            args = call_arguments
        result = await sync_to_async(self._sync_call)(endpoint, args)
        text = result if isinstance(result, str) else json.dumps(result)
        return [TextContent(type="text", text=text)]

    def _sync_call(self, endpoint: MCPEndpoint, args: Any) -> Any:
        """
        Synchronous implementation of the tool logic.

        ``args`` is a validated instance of ``input_schema`` (a pydantic model)
        when ``input_schema`` is set, otherwise the raw dict.

        Return a string for plain-text responses or any JSON-serialisable
        value.  Raise an exception to signal an error to the client.
        """
        raise NotImplementedError("Implement _sync_call or override call.")


class MCPToolRegistry(Registry[MCPTool]):
    name = "mcp_tools"

    async def list_all_tools(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """Return only *enabled* tools available to the given endpoint user."""
        all_tools: List["Tool"] = []
        for mcp in self.registry.values():
            if not mcp.enabled:
                continue
            tools = await mcp.list(endpoint)
            all_tools.extend(tools)
        return all_tools

    def match_by_name(self, name: str) -> Optional[MCPTool]:
        """Return the tool registered under ``name``, or None."""
        return self.registry.get(name)


mcp_tool_registry = MCPToolRegistry()
