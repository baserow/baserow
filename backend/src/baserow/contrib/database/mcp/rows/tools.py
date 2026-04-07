from baserow.contrib.database.mcp import services
from baserow.contrib.database.mcp.rows.schemas import (
    CreateRowsInput,
    DeleteRowsInput,
    ListRowsInput,
    UpdateRowsInput,
)
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool


class ListRowsMcpTool(MCPTool):
    """
    List rows from a table with optional search and pagination.
    Returns rows with user-facing field names as keys.
    """

    type = "list_table_rows"
    input_schema = ListRowsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: ListRowsInput) -> dict:
        return services.list_rows(
            endpoint.user,
            endpoint.workspace,
            args.table_id,
            search=args.search or "",
            page=args.page,
            size=args.size,
        )


class CreateRowsMcpTool(MCPTool):
    """
    Create one or more rows in a table.
    Call get_table_schema first to learn the field names and types.
    Use user-facing field names as keys, not internal field IDs.
    """

    type = "create_rows"
    input_schema = CreateRowsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: CreateRowsInput) -> list[dict]:
        return services.create_rows(
            endpoint.user, endpoint.workspace, args.table_id, args.rows
        )


class UpdateRowsMcpTool(MCPTool):
    """
    Update one or more existing rows in a table.
    Each row must include 'id' plus the fields to update.
    Call get_table_schema first to learn the field names.
    Use user-facing field names as keys, not internal field IDs.
    """

    type = "update_rows"
    input_schema = UpdateRowsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: UpdateRowsInput) -> list[dict]:
        return services.update_rows(
            endpoint.user,
            endpoint.workspace,
            args.table_id,
            [r.model_dump() for r in args.rows],
        )


class DeleteRowsMcpTool(MCPTool):
    """
    Delete one or more rows from a table by ID.
    Use list_table_rows to find row IDs first.
    """

    type = "delete_rows"
    input_schema = DeleteRowsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: DeleteRowsInput) -> str:
        services.delete_rows(
            endpoint.user, endpoint.workspace, args.table_id, args.row_ids
        )
        return "Rows successfully deleted."
