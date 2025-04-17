from asgiref.sync import sync_to_async
from mcp import Tool
from mcp.types import TextContent
from rest_framework.response import Response
from starlette.status import HTTP_204_NO_CONTENT

from baserow.contrib.database.api.rows.serializers import get_row_serializer_class
from baserow.contrib.database.mcp.table.utils import (
    get_all_tables,
    remove_table_no_permission,
    table_in_workspace_of_endpoint,
)
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
)
from baserow.core.mcp.registries import MCPTool
from baserow.core.mcp.utils import internal_api_request, serializer_to_openapi_inline


class ListRowsMcpTool(MCPTool):
    type = "list_table_rows"
    name = "list_rows_table_{id}"

    async def list(self, endpoint):
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
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Optionally search in the whole table.",
                            },
                            "page": {
                                "type": "integer",
                                "default": 1,
                                "description": "Rows/records are paginated. Provide "
                                "if a different page should be fetched.",
                            },
                            "size": {
                                "type": "integer",
                                "default": 100,
                                "description": "Maximum rows/records that must be "
                                "returned.",
                            },
                        },
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
        table_id = name_parameters["id"]
        if not await sync_to_async(table_in_workspace_of_endpoint)(endpoint, table_id):
            return [TextContent(type="text", text="Table not in endpoint workspace.")]

        search = call_arguments.get("search", "")
        page = call_arguments.get("page", 1)
        size = call_arguments.get("size", 100)

        response: Response = await sync_to_async(internal_api_request)(
            "api:database:rows:list",
            path_params={"table_id": table_id},
            user=endpoint.user,
            query_params={
                "user_field_names": "true",
                "search": search,
                "page": page,
                "size": size,
            },
        )

        return [TextContent(type="text", text=response.content)]


class CreateRowMcpTool(MCPTool):
    type = "create_table_row"
    name = "create_row_table_{id}"

    async def list(self, endpoint):
        tables = await sync_to_async(get_all_tables)(endpoint)
        tables = await sync_to_async(remove_table_no_permission)(
            endpoint, tables, CreateRowDatabaseTableOperationType
        )

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
        table_id = name_parameters["id"]
        if not await sync_to_async(table_in_workspace_of_endpoint)(endpoint, table_id):
            return [TextContent(type="text", text="Table not in endpoint workspace.")]

        response: Response = await sync_to_async(internal_api_request)(
            "api:database:rows:list",
            method="POST",
            path_params={"table_id": name_parameters["id"]},
            user=endpoint.user,
            data=call_arguments["row"],
            query_params={"user_field_names": "true"},
        )

        return [TextContent(type="text", text=response.content)]


class UpdateRowMcpTool(MCPTool):
    type = "update_table_row"
    name = "update_row_table_{id}"

    async def list(self, endpoint):
        tables = await sync_to_async(get_all_tables)(endpoint)
        tables = await sync_to_async(remove_table_no_permission)(
            endpoint, tables, UpdateDatabaseRowOperationType
        )

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
        table_id = name_parameters["id"]
        if not await sync_to_async(table_in_workspace_of_endpoint)(endpoint, table_id):
            return [TextContent(type="text", text="Table not in endpoint workspace.")]

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

        return [TextContent(type="text", text=response.content)]


class DeleteRowMcpTool(MCPTool):
    type = "delete_table_row"
    name = "delete_row_table_{id}"

    async def list(self, endpoint):
        tables = await sync_to_async(get_all_tables)(endpoint)
        tables = await sync_to_async(remove_table_no_permission)(
            endpoint, tables, DeleteDatabaseRowOperationType
        )

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
        table_id = name_parameters["id"]
        if not await sync_to_async(table_in_workspace_of_endpoint)(endpoint, table_id):
            return [TextContent(type="text", text="Table not in endpoint workspace.")]

        response: Response = await sync_to_async(internal_api_request)(
            "api:database:rows:item",
            method="DELETE",
            path_params={
                "table_id": name_parameters["id"],
                "row_id": call_arguments["id"],
            },
            user=endpoint.user,
        )

        content = (
            "successfully deleted"
            if response.status_code == HTTP_204_NO_CONTENT
            else response.content
        )
        return [TextContent(type="text", text=content)]
