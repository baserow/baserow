from baserow.contrib.database.tools import fields
from baserow.core.mcp.groups import GROUP_DATABASE_DELETE, GROUP_DATABASE_EDIT
from baserow.core.mcp.registries import FunctionMCPTool


class CreateFieldsMcpTool(FunctionMCPTool):
    type = "create_fields"
    group = GROUP_DATABASE_EDIT
    title = "Create fields"
    read_only = False
    destructive = False
    function = fields.create_fields


class UpdateFieldsMcpTool(FunctionMCPTool):
    type = "update_fields"
    group = GROUP_DATABASE_EDIT
    title = "Update fields"
    read_only = False
    destructive = True
    function = fields.update_fields


class DeleteFieldsMcpTool(FunctionMCPTool):
    type = "delete_fields"
    group = GROUP_DATABASE_DELETE
    title = "Delete fields"
    read_only = False
    destructive = True
    function = fields.delete_fields
