from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.utils import NameRoute
from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from mcp import Tool
    from mcp.types import EmbeddedResource, ImageContent, TextContent


class MCPTool(Instance):
    name = None
    """
    Unique name of the tool. This is used to route the tool call to this instance. It
    can contain name parameters, like `{id}`. If provided, then it will dynamically
    route all calls to this tool. This can be used to generate dynamic tools.
    """

    def get_name(self):
        if self.name is None:
            raise NotImplementedError(
                "Either the `name` property or `get_name` method must be implemented."
            )
        return self.name

    async def list(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """
        :param endpoint: The endpoint related to the request. Can be used to
            dynamically check which tools the user has access to.
        :return: List of all the available tools to the user.
        """

        raise NotImplementedError("The `list` method must be implemented.")

    async def call(
        self,
        endpoint: MCPEndpoint,
        name_parameters: Dict[str, Any],
        call_arguments: Dict[str, Any],
    ) -> Sequence[Union["TextContent", "ImageContent", "EmbeddedResource"]]:
        """

        :param endpoint: The endpoint related to the authenticated user.
        :param name_parameters: A dict containing the provided name params defined in
            the `name` property like {id}.
        :param call_arguments: A dict containing the validated arguments from the
            tool inputSchema.
        :return: The response of the call.
        """

        raise NotImplementedError("The `call` method must be implemented.")

    def resolve_name(self, **kwargs):
        return self.name.format(**kwargs)


class MCPToolRegistry(Registry[MCPTool]):
    name = "mcp_tools"

    async def list_all_tools(self, endpoint: MCPEndpoint) -> List["Tool"]:
        """
        :param endpoint: The endpoint related to the request. Can be used to
            dynamically check which tools the user has access to.
        :return: List of all the available tools to the provided user.
        """

        all_tools = []
        for mcp in self.registry.values():
            tools = await mcp.list(endpoint)
            all_tools.extend(tools)
        return all_tools

    def match_by_name(self, name: str) -> Union[Optional[MCPTool], Optional[dict]]:
        """
        Tries to find a matching tool by the name route, including the resolving of
        the parameters like `{id}`.

        :param name: The name of the tool that must be matched.
        :return: Returns the matching tool and the extracts params.
        """

        for tool in self.registry.values():
            tool_name = NameRoute(tool.name)
            params = tool_name.match(name)
            if params is not None:
                return tool, params
        return None, None


mcp_tool_registry = MCPToolRegistry()
