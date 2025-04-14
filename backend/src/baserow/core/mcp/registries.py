from typing import Any, Dict, List, Sequence, TYPE_CHECKING, Optional, Union

from django.contrib.auth.models import AbstractUser

from mcp import Tool
from mcp.types import EmbeddedResource, ImageContent, TextContent

from baserow.core.mcp.utils import NameRoute
from baserow.core.registry import Instance, Registry


"""
        from drf_spectacular import serializers
        from .utils import serializer_to_openapi_inline

        token = current_token.get()
        print(f"[list_tools] token: {token}")

        schema = serializer_to_openapi_inline(DiscriminatorCustomFieldsMappingSerializer(
            view_type_registry, CreateViewSerializer
        ))

        return [
            MCPTool(
                name="create_test",
                description=f"This is a test tool for token: {token}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "test": schema
                    },
                    "required": [
                        "test"
                    ]
                }
            )
        ]
"""


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

    async def list(self, user: AbstractUser) -> List[Tool]:
        """
        :param user: The authenticated user object. Can be used to dynamically check
            which tools the user has access to.
        :return: List of all the available tools to the user.
        """

        raise NotImplementedError("The `list` method must be implemented.")

    async def call(
        self,
        user: AbstractUser,
        name_parameters: Dict[str, Any],
        call_arguments: Dict[str, Any],
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """

        :param user: The authenticated user object. Can be used to dynamically check
            the permissions.
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

    async def list_all_tools(self, user: AbstractUser) -> List[Tool]:
        """
        :param user: The authenticated user object. Can be used to dynamically check
            which tools the user has access to.
        :return: List of all the available tools to the provided user.
        """

        all_tools = []
        for mcp in self.registry.values():
            tools = await mcp.list(user)
            all_tools.extend(tools)
        return tools

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
            if params:
                return tool, params
        return None, None



mcp_tool_registry = MCPToolRegistry()
