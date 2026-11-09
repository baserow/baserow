from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import actions

# "element" sets these apart from automation actions, which are nodes.


class ListElementActionsMcpTool(FunctionMCPTool):
    type = "list_element_actions"
    group = GROUP_BUILDER_READ
    title = "List workflow actions"
    read_only = True
    function = actions.list_element_actions


class CreateElementActionsMcpTool(FunctionMCPTool):
    type = "create_element_actions"
    group = GROUP_BUILDER_EDIT
    title = "Create workflow actions"
    read_only = False
    destructive = False
    function = actions.create_element_actions


class UpdateElementActionMcpTool(FunctionMCPTool):
    type = "update_element_action"
    group = GROUP_BUILDER_EDIT
    title = "Change a workflow action"
    read_only = False
    destructive = True
    function = actions.update_element_action
