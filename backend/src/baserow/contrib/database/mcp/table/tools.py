from baserow.contrib.database.mcp import services
from baserow.contrib.database.mcp.table.schemas import (
    CreateDatabaseInput,
    CreateTableInput,
    DeleteTableInput,
    GetTableSchemaInput,
    ListDatabasesInput,
    ListTablesInput,
    UpdateTableInput,
)
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool


class ListDatabasesMcpTool(MCPTool):
    """
    List all databases in the workspace.
    Use this to discover database IDs before listing tables.
    """

    type = "list_databases"
    input_schema = ListDatabasesInput

    def _sync_call(self, endpoint: MCPEndpoint, args: ListDatabasesInput) -> list[dict]:
        databases = services.list_databases(endpoint.user, endpoint.workspace)
        return [{"id": db.id, "name": db.name, "order": db.order} for db in databases]


class CreateDatabaseMcpTool(MCPTool):
    """
    Create a new database in the workspace.
    Returns the new database ID and name.
    """

    type = "create_database"
    enabled = False
    input_schema = CreateDatabaseInput

    def _sync_call(self, endpoint: MCPEndpoint, args: CreateDatabaseInput) -> dict:
        db = services.create_database(endpoint.user, endpoint.workspace, args.name)
        return {"id": db.id, "name": db.name}


class ListTablesMcpTool(MCPTool):
    """
    List all tables in the workspace, optionally filtered by database.
    Use this to discover table IDs before calling get_table_schema.
    """

    type = "list_tables"
    input_schema = ListTablesInput

    def _sync_call(self, endpoint: MCPEndpoint, args: ListTablesInput) -> list[dict]:
        tables = services.list_tables(
            endpoint.user, endpoint.workspace, database_id=args.database_id
        )
        return [
            {
                "id": t.id,
                "name": t.name,
                "order": t.order,
                "database_id": t.database_id,
            }
            for t in tables
        ]


class CreateTableMcpTool(MCPTool):
    """
    Create a new table in a database, optionally with initial fields.
    Fields are created in dependency order (regular → link_row → lookup → formula).
    For link_row fields, the linked table must already exist.
    """

    type = "create_table"
    enabled = False
    input_schema = CreateTableInput

    def _sync_call(self, endpoint: MCPEndpoint, args: CreateTableInput) -> dict:
        return services.create_table(
            endpoint.user,
            endpoint.workspace,
            args.database_id,
            args.name,
            [f.model_dump() for f in args.fields] if args.fields else None,
        )


class UpdateTableMcpTool(MCPTool):
    """
    Rename an existing table.
    Call list_tables first to get the table ID.
    """

    type = "update_table"
    enabled = False
    input_schema = UpdateTableInput

    def _sync_call(self, endpoint: MCPEndpoint, args: UpdateTableInput) -> dict:
        return services.update_table(
            endpoint.user, endpoint.workspace, args.table_id, args.name
        )


class DeleteTableMcpTool(MCPTool):
    """
    Delete (trash) a table and all its rows.
    The table can be restored from trash afterwards.
    """

    type = "delete_table"
    enabled = False
    input_schema = DeleteTableInput

    def _sync_call(self, endpoint: MCPEndpoint, args: DeleteTableInput) -> str:
        services.delete_table(endpoint.user, endpoint.workspace, args.table_id)
        return "Table successfully deleted."


class GetTableSchemaMcpTool(MCPTool):
    """
    Get the field schema for one or more tables.
    Call this before create_rows or update_rows to learn the field
    names and types accepted by those tools.
    """

    type = "get_table_schema"
    input_schema = GetTableSchemaInput

    def _sync_call(
        self, endpoint: MCPEndpoint, args: GetTableSchemaInput
    ) -> list[dict]:
        return services.get_table_schema(
            endpoint.user, endpoint.workspace, args.table_ids
        )
