from baserow.core.mcp.groups import GROUP_WORKSPACE_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow.core.tools import search


class SearchWorkspaceMcpTool(FunctionMCPTool):
    type = "search_workspace"
    group = GROUP_WORKSPACE_READ
    title = "Search the workspace"
    read_only = True
    function = search.search_workspace
