from asgiref.sync import sync_to_async
from mcp import Tool
from mcp.types import TextContent
from rest_framework.response import Response

from baserow.contrib.database.api.rows.serializers import get_row_serializer_class
from baserow.core.mcp.registries import MCPTool
from baserow.core.mcp.utils import internal_api_request, serializer_to_openapi_inline
from baserow.contrib.database.mcp.table.utils import get_all_tables


class ListRowsMcpTool(MCPTool):
    type = "list_table_rows"
    name = "list_rows_table_{id}"

    async def list(self, endpoint):
        # @TODO make sure more efficient.
        tables = await sync_to_async(get_all_tables)(endpoint)

        tools = []
        for table in tables:
            tools.append(
                Tool(
                    name=self.resolve_name(id=table.id),
                    description=f"Lists all the rows/records in table with id {table.id}, "
                    f'named "{table.name}".',
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                )
            )
        return tools

    async def call(
        self,
        endpoint,
        name,
        name_parameters,
        call_arguments,
    ):
        # @TODO introduce a check to see if the user has access to the table, and if it
        #  belongs to the workspace of the endpoint.

        response: Response = await sync_to_async(internal_api_request)(
            "api:database:rows:list",
            path_params={"table_id": name_parameters["id"]},
            user=endpoint.user,
            query_params={"user_field_names": "true"},
        )
        # @TODO remove the pagination in the response.

        return [TextContent(type="text", text=response.content)]


class CreateRowMcpTool(MCPTool):
    type = "create_table_row"
    name = "create_row_table_{id}"

    async def list(self, endpoint):
        # @TODO make sure more efficient, and check if the user can write into the
        #  table.
        tables = await sync_to_async(get_all_tables)(endpoint)

        tools = []
        for table in tables:
            model = await sync_to_async(table.get_model)()
            validation_serializer = get_row_serializer_class(
                model, user_field_names=True
            )
            spec = serializer_to_openapi_inline(
                validation_serializer, "POST", "request"
            )

            tools.append(
                Tool(
                    name=self.resolve_name(id=table.id),
                    description=f"Create a new row/record in table with id {table.id}, "
                    f'named "{table.name}".',
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "row": spec,
                        },
                        "required": ["row"],
                    },
                )
            )
        return tools

    async def call(
        self,
        endpoint,
        name,
        name_parameters,
        call_arguments,
    ):
        # @TODO introduce a check to see if the user has access to the table, and if it
        #  belongs to the workspace of the endpoint.

        try:
            response: Response = await sync_to_async(internal_api_request)(
                "api:database:rows:list",
                method="POST",
                path_params={"table_id": name_parameters["id"]},
                user=endpoint.user,
                data=call_arguments["row"],
                query_params={"user_field_names": "true"},
            )
        except Exception as e:
            import traceback

            traceback.print_exception(type(e), e, e.__traceback__)

        return [TextContent(type="text", text=response.content)]


class UpdateRowMcpTool(MCPTool):
    type = "update_table_row"
    name = "update_row_table_{id}"

    async def list(self, endpoint):
        # @TODO make sure more efficient, and check if the user can write into the
        #  table.
        tables = await sync_to_async(get_all_tables)(endpoint)

        tools = []
        for table in tables:
            model = await sync_to_async(table.get_model)()
            validation_serializer = get_row_serializer_class(
                model, user_field_names=True
            )
            spec = serializer_to_openapi_inline(
                validation_serializer, "PATCH", "request"
            )

            tools.append(
                Tool(
                    name=self.resolve_name(id=table.id),
                    description=f"Create a new row/record in table with id {table.id}, "
                    f'named "{table.name}".',
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "integer",
                            },
                            "row": spec,
                        },
                        "required": ["id", "row"],
                    },
                )
            )
        return tools

    async def call(
        self,
        endpoint,
        name,
        name_parameters,
        call_arguments,
    ):
        # @TODO introduce a check to see if the user has access to the table, and if it
        #  belongs to the workspace of the endpoint.

        try:
            response: Response = await sync_to_async(internal_api_request)(
                "api:database:rows:item",
                method="PATCH",
                path_params={
                    "table_id": name_parameters["id"],
                    "row_id": call_arguments["id"],
                },
                user=endpoint.user,
                data=call_arguments["row"],
                query_params={"user_field_names": "true"},
            )
        except Exception as e:
            import traceback

            traceback.print_exception(type(e), e, e.__traceback__)

        return [TextContent(type="text", text=response.content)]


class DeleteRowMcpTool(MCPTool):
    type = "delete_table_row"
    name = "delete_row_table_{id}"

    async def list(self, endpoint):
        # @TODO make sure more efficient, and check if the user can write into the
        #  table.
        tables = await sync_to_async(get_all_tables)(endpoint)

        tools = []
        for table in tables:
            tools.append(
                Tool(
                    name=self.resolve_name(id=table.id),
                    description=f"Create a new row/record in table with id {table.id}, "
                    f'named "{table.name}".',
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "integer",
                            },
                        },
                        "required": ["id"],
                    },
                )
            )
        return tools

    async def call(
        self,
        endpoint,
        name,
        name_parameters,
        call_arguments,
    ):
        # @TODO introduce a check to see if the user has access to the table, and if it
        #  belongs to the workspace of the endpoint.

        try:
            response: Response = await sync_to_async(internal_api_request)(
                "api:database:rows:item",
                method="DELETE",
                path_params={
                    "table_id": name_parameters["id"],
                    "row_id": call_arguments["id"],
                },
                user=endpoint.user,
            )
        except Exception as e:
            import traceback

            traceback.print_exception(type(e), e, e.__traceback__)

        return [TextContent(type="text", text=response.content)]
