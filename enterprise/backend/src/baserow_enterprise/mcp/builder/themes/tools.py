from baserow.core.mcp.groups import GROUP_BUILDER_EDIT
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import themes


class SetThemeMcpTool(FunctionMCPTool):
    type = "set_theme"
    group = GROUP_BUILDER_EDIT
    title = "Set the theme"
    read_only = False
    destructive = True
    function = themes.set_theme
