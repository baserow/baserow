from baserow.contrib.database.mcp import services
from baserow.contrib.database.mcp.fields.schemas import (
    CreateFieldsInput,
    DeleteFieldsInput,
    UpdateFieldsInput,
)
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool


class CreateFieldsMcpTool(MCPTool):
    """
    Add one or more fields to an existing table.
    Call get_table_schema first to see existing fields and avoid duplicates.
    Fields are created in dependency order (regular → link_row → lookup → formula).
    For link_row fields, the linked table must already exist.
    """

    type = "create_fields"
    enabled = False
    input_schema = CreateFieldsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: CreateFieldsInput) -> list[dict]:
        return services.create_fields(
            endpoint.user,
            endpoint.workspace,
            args.table_id,
            [f.model_dump() for f in args.fields],
        )


class UpdateFieldsMcpTool(MCPTool):
    """
    Update one or more existing fields (rename, change type, change properties).
    Call get_table_schema first to get field IDs and current types.
    """

    type = "update_fields"
    enabled = False
    input_schema = UpdateFieldsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: UpdateFieldsInput) -> list[dict]:
        return services.update_fields(
            endpoint.user, endpoint.workspace, [f.model_dump() for f in args.fields]
        )


class DeleteFieldsMcpTool(MCPTool):
    """
    Delete (trash) one or more fields by ID.
    Primary fields cannot be deleted.
    Call get_table_schema first to confirm field IDs.
    """

    type = "delete_fields"
    enabled = False
    input_schema = DeleteFieldsInput

    def _sync_call(self, endpoint: MCPEndpoint, args: DeleteFieldsInput) -> str:
        services.delete_fields(endpoint.user, endpoint.workspace, args.field_ids)
        return "Fields successfully deleted."
