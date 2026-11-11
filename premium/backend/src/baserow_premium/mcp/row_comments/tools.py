from baserow.core.mcp.groups import GROUP_DATABASE_EDIT, GROUP_DATABASE_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_premium.row_comments import tools


class ListRowCommentsMcpTool(FunctionMCPTool):
    type = "list_row_comments"
    group = GROUP_DATABASE_READ
    title = "List row comments"
    read_only = True
    function = tools.list_row_comments


class CreateRowCommentsMcpTool(FunctionMCPTool):
    type = "create_row_comments"
    group = GROUP_DATABASE_EDIT
    title = "Create row comments"
    read_only = False
    destructive = False
    function = tools.create_row_comments
