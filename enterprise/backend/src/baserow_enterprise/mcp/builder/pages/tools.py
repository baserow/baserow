from baserow.core.mcp.groups import GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import pages


class ListPagesMcpTool(FunctionMCPTool):
    type = "list_pages"
    group = GROUP_BUILDER_READ
    title = "List pages"
    read_only = True
    function = pages.list_pages
