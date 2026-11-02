import inspect
import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Union,
    get_type_hints,
)

from asgiref.sync import sync_to_async
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.exceptions import MCPToolInputError, format_validation_error
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

    title: str | None = None
    """Human-readable tool name shown by MCP clients."""

    read_only: bool = False
    """True when the tool never changes data. Clients skip confirmation."""

    destructive: bool = False
    """True when the tool can overwrite or delete data. Clients always confirm."""

    open_world: bool = False
    """True when the tool reaches outside the endpoint's workspace."""

    group: str | None = None
    """The permission group the tool belongs to, see ``baserow.core.mcp.groups``."""

    off_by_default: bool = False
    """True to leave a read-only tool off new endpoint keys, because what it reads
    needs a deliberate choice. The user can turn it on."""

    @property
    def name(self) -> str:
        """MCP tool name, derived from ``type``."""
        return self.type

    def get_name(self) -> str:
        return self.type

    @property
    def display_title(self) -> str:
        """``title``, or a readable fallback derived from ``type``."""
        return self.title or self.type.replace("_", " ").capitalize()

    def get_description(self) -> str | None:
        """The MCP tool description, by default the class docstring."""

        return self.__class__.__doc__

    async def list(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """
        Return the MCP Tool definition(s) for this tool.

        The default implementation builds a single Tool from ``type``
        (as name), the class docstring (as description) and
        ``input_schema``. Override for custom behaviour.
        """
        from mcp import Tool
        from mcp.types import ToolAnnotations

        schema = (
            self.input_schema.model_json_schema()
            if self.input_schema
            else {"type": "object", "properties": {}}
        )
        description = self.get_description()
        if description:
            description = " ".join(description.split())
        annotations = ToolAnnotations(
            title=self.display_title,
            readOnlyHint=self.read_only,
            destructiveHint=self.destructive,
            openWorldHint=self.open_world,
        )
        return [
            Tool(
                name=self.type,
                description=description,
                inputSchema=schema,
                annotations=annotations,
            )
        ]

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
            try:
                args = self.input_schema(**call_arguments)
            except ValidationError as exc:
                raise MCPToolInputError(format_validation_error(exc)) from exc
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


def _input_model_for(
    function: Callable, name: str, extra: str = "forbid"
) -> type[BaseModel]:
    """
    Builds the input model of a shared tool from its signature. The first
    parameter is the ``ToolContext`` and isn't part of the input.
    """

    hints = get_type_hints(function, include_extras=True)
    parameters = list(inspect.signature(function).parameters.values())[1:]
    fields = {
        parameter.name: (
            hints[parameter.name],
            ... if parameter.default is inspect.Parameter.empty else parameter.default,
        )
        for parameter in parameters
    }
    return create_model(f"{name}_input", __config__=ConfigDict(extra=extra), **fields)


class FunctionMCPTool(MCPTool):
    """
    Offers a tool shared with the other clients over MCP, see
    ``baserow.core.tools``. Subclasses set ``function`` and the MCP metadata. The
    input schema comes from the function's signature and the description from its
    docstring.
    """

    function: Callable[..., Any]

    ignore_extra_arguments: bool = False
    """True to drop unknown arguments instead of rejecting the call."""

    def __init__(self):
        super().__init__()
        self.input_schema = _input_model_for(
            type(self).function,
            self.type,
            extra="ignore" if self.ignore_extra_arguments else "forbid",
        )

    def get_description(self) -> str | None:
        return type(self).function.__doc__

    def _sync_call(self, endpoint: MCPEndpoint, args: BaseModel) -> Any:
        from baserow.core.tools import ToolContext

        kwargs = {name: getattr(args, name) for name in type(args).model_fields}
        return type(self).function(
            ToolContext(
                user=endpoint.user,
                workspace=endpoint.workspace,
                timezone=endpoint.user.profile.timezone,
            ),
            **kwargs,
        )


class MCPToolRegistry(Registry[MCPTool]):
    name = "mcp_tools"

    def get_enabled_tools(self) -> List[MCPTool]:
        """Return the enabled tools, in registration order."""
        return [tool for tool in self.registry.values() if tool.enabled]

    @staticmethod
    def get_allowed_names(endpoint: MCPEndpoint) -> List[str]:
        """
        The tool names stored on the endpoint. ``None`` is only left by code that
        ran before the allow-lists were filled in, and means ``LEGACY_DEFAULT_TOOLS``.
        """

        if endpoint.allowed_tools is None:
            return list(LEGACY_DEFAULT_TOOLS)
        return list(endpoint.allowed_tools)

    def get_allowed_tools(self, endpoint: MCPEndpoint) -> List[MCPTool]:
        """
        Return the enabled tools the endpoint may use. ``allowed_tools = None``
        allows the ``LEGACY_DEFAULT_TOOLS`` that are enabled.
        """
        allowed = set(self.get_allowed_names(endpoint))
        return [tool for tool in self.get_enabled_tools() if tool.name in allowed]

    async def list_all_tools(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """Return the enabled tools the given endpoint is allowed to use."""
        all_tools: List["Tool"] = []
        for mcp in await sync_to_async(self.get_allowed_tools)(endpoint):
            tools = await mcp.list(endpoint)
            all_tools.extend(tools)
        return all_tools

    def match_by_name(self, name: str) -> Optional[MCPTool]:
        """Return the tool registered under ``name``, or None."""
        return self.registry.get(name)

    def get_allowed_tool(self, endpoint: MCPEndpoint, name: str) -> Optional[MCPTool]:
        """Return the tool called ``name`` if the endpoint may call it, or None."""
        tool = self.match_by_name(name)
        if tool is None or not tool.enabled:
            return None
        if name not in self.get_allowed_names(endpoint):
            return None
        return tool


mcp_tool_registry = MCPToolRegistry()
