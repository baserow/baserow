from baserow.core.mcp.groups import GROUP_DATABASE_EDIT, GROUP_DATABASE_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_premium.row_comments import tools


class RowCommentMcpTool(FunctionMCPTool):
    def get_description(self) -> str:
        return f"{super().get_description().strip()} Needs a premium licence."


class ListRowCommentsMcpTool(RowCommentMcpTool):
    type = "list_row_comments"
    group = GROUP_DATABASE_READ
    title = "List row comments"
    read_only = True
    function = tools.list_row_comments


class SearchRowCommentsMcpTool(RowCommentMcpTool):
    type = "search_row_comments"
    group = GROUP_DATABASE_READ
    title = "Search row comments"
    read_only = True
    function = tools.search_row_comments


class CreateRowCommentsMcpTool(RowCommentMcpTool):
    type = "create_row_comments"
    group = GROUP_DATABASE_EDIT
    title = "Create row comments"
    read_only = False
    destructive = False
    function = tools.create_row_comments
