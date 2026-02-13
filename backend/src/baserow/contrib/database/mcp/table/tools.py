import json

from asgiref.sync import sync_to_async

from baserow.contrib.database.api.tables.serializers import (
    TableWithoutDataSyncSerializer,
)
from baserow.contrib.database.mcp.table.utils import get_all_tables
from baserow.core.mcp.registries import MCPTool


class ListTablesMcpTool(MCPTool):
    type = "list_tables"
    name = "list_tables"

    async def list(self, endpoint):
        from mcp import Tool

        return [
            Tool(
                name=self.name,
                description=f"Lists all the tables.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            )
        ]

    async def call(
        self,
        endpoint,
        name,
        name_parameters,
        call_arguments,
    ):
        from mcp.types import TextContent

        tables = await sync_to_async(get_all_tables)(endpoint)
        serializer = TableWithoutDataSyncSerializer(tables, many=True)
        table_json = json.dumps(serializer.data)
        return [TextContent(type="text", text=table_json)]
