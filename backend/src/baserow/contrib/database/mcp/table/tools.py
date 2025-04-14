from asgiref.sync import sync_to_async
from django.http import HttpResponse
from mcp import Tool
from mcp.types import TextContent
from rest_framework.response import Response

from baserow.contrib.database.api.rows.serializers import get_row_serializer_class
from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.mcp.registries import MCPTool
from baserow.core.mcp.utils import serializer_to_openapi_inline, internal_api_request

from django.test import Client


def get_all_tables(user):
    workspace = user.workspaceuser_set.all().select_related("workspace").first().workspace
    tables_qs = Table.objects.filter(database__workspace_id=workspace.id).select_related("database__workspace")
    return list(CoreHandler().filter_queryset(
        user,
        ListTablesDatabaseTableOperationType.type,
        tables_qs,
        workspace=workspace,
    ))


class ListRowsMcpTool(MCPTool):
    type = "list_table_rows"
    name = "list_rows_table_{id}"

    async def list(self, user):
        tables = await sync_to_async(get_all_tables)(user)

        tools = []
        for table in tables:
            tools.append(Tool(
                name=self.resolve_name(id=table.id),
                description=f"Lists all the rows/records in table with id {table.id}, "
                            f"named \"{table.name}\".",
                inputSchema={
                    "type": "object",
                    "properties": {},
                }
            ))
        return tools

    async def call(
        self,
        user,
        name,
        name_parameters,
        call_arguments,
    ):
        response: Response = await sync_to_async(internal_api_request

        )("api:database:rows:list",
           path_params={"table_id": name_parameters["id"]},
           user=user,)

        return [
            TextContent(
                type="text", text=response.content
            )
        ]

#
# class CreateTableRowMcpTool(MCPTool):
#     type = "create_table_row"
#     name = "create_row_table_{id}"
#
#     async def list(self, user):
#         tables = await sync_to_async(get_all_tables)(user)
#
#         tools = []
#         for table in tables:
#             model = await sync_to_async(table.get_model)()
#             serializer_class = get_row_serializer_class(
#                 model, user_field_names=True
#             )
#             tools.append(Tool(
#                 name=self.resolve_name(id=table.id),
#                 description=f"Lists all the rows/records in table with id {table.id}, "
#                             f"named \"{table.name}\".",
#                 inputSchema=serializer_to_openapi_inline(serializer_class)
#             ))
#         return tools
#
#     async def call(
#         self,
#         user,
#         name,
#         name_parameters,
#         call_arguments,
#     ):
#         print(user.id)
#         print(name)
#         print(name_parameters)
#         print(call_arguments)
#         return [
#             TextContent(
#                 type="text", text=f"Tool '{name}' called with user: " f"{user.email}"
#             )
#         ]
