from baserow.core.mcp.groups import GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import elements


class ListElementsMcpTool(FunctionMCPTool):
    type = "list_elements"
    group = GROUP_BUILDER_READ
    title = "List elements"
    read_only = True
    function = elements.list_elements
