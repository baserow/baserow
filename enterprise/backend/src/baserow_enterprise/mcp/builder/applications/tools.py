from baserow.core.mcp.groups import GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import applications


class ListBuildersMcpTool(FunctionMCPTool):
    type = "list_builders"
    group = GROUP_BUILDER_READ
    title = "List application builders"
    read_only = True
    function = applications.list_builders
