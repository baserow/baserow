from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import actions


class ListActionsMcpTool(FunctionMCPTool):
    type = "list_actions"
    group = GROUP_BUILDER_READ
    title = "List workflow actions"
    read_only = True
    function = actions.list_actions


class CreateActionsMcpTool(FunctionMCPTool):
    type = "create_actions"
    group = GROUP_BUILDER_EDIT
    title = "Create workflow actions"
    read_only = False
    destructive = False
    function = actions.create_actions


class AddActionFieldMappingMcpTool(FunctionMCPTool):
    type = "add_action_field_mapping"
    group = GROUP_BUILDER_EDIT
    title = "Set a field of a row action"
    read_only = False
    destructive = False
    function = actions.add_action_field_mapping
