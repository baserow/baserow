from baserow.contrib.builder.tools import themes
from baserow.core.mcp.groups import GROUP_BUILDER_EDIT
from baserow.core.mcp.registries import FunctionMCPTool


class SetThemeMcpTool(FunctionMCPTool):
    type = "set_theme"
    group = GROUP_BUILDER_EDIT
    title = "Set the theme"
    read_only = False
    destructive = True
    function = themes.set_theme
