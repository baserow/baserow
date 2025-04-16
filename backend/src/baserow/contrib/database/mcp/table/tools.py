from asgiref.sync import sync_to_async
from mcp import Tool
from mcp.types import TextContent
from rest_framework.response import Response

from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.mcp.registries import MCPTool
from baserow.core.mcp.utils import internal_api_request


def get_all_tables(endpoint):
    workspace = endpoint.workspace
    tables_qs = Table.objects.filter(
        database__workspace_id=workspace.id
    ).select_related("database__workspace")
    return list(
        CoreHandler().filter_queryset(
            endpoint.user,
            ListTablesDatabaseTableOperationType.type,
            tables_qs,
            workspace=workspace,
        )
    )


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
        )

        return [TextContent(type="text", text=response.content)]
