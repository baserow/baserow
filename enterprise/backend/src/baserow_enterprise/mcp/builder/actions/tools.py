from baserow.core.mcp.groups import GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import actions


class ListActionsMcpTool(FunctionMCPTool):
    type = "list_actions"
    group = GROUP_BUILDER_READ
    title = "List workflow actions"
    read_only = True
    function = actions.list_actions
