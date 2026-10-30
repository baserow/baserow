from typing import Any

from pydantic import BaseModel

from baserow.contrib.database.mcp import services
from baserow.contrib.database.tools import rows
from baserow.core.mcp.groups import (
    GROUP_DATABASE_DELETE,
    GROUP_DATABASE_EDIT,
    GROUP_DATABASE_READ,
)
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import FunctionMCPTool


class RowChangeMcpTool(FunctionMCPTool):
    """Reports the row errors a client causes with the REST API's message."""

    def _sync_call(self, endpoint: MCPEndpoint, args: BaseModel) -> Any:
        with services.input_errors():
            return super()._sync_call(endpoint, args)


class ListRowsMcpTool(FunctionMCPTool):
    type = "list_table_rows"
    group = GROUP_DATABASE_READ
    title = "List rows"
    read_only = True
    function = rows.list_table_rows


class CreateRowsMcpTool(RowChangeMcpTool):
    type = "create_rows"
    group = GROUP_DATABASE_EDIT
    title = "Create rows"
    function = rows.create_rows


class UpdateRowsMcpTool(RowChangeMcpTool):
    type = "update_rows"
    group = GROUP_DATABASE_EDIT
    title = "Update rows"
    destructive = True
    function = rows.update_rows


class DeleteRowsMcpTool(RowChangeMcpTool):
    type = "delete_rows"
    group = GROUP_DATABASE_DELETE
    title = "Delete rows"
    destructive = True
    function = rows.delete_rows
