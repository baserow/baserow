from baserow.core.mcp.groups import GROUP_BUILDER_EDIT
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import user_sources


class SetupUserSourceMcpTool(FunctionMCPTool):
    type = "setup_user_source"
    group = GROUP_BUILDER_EDIT
    title = "Set up a user source"
    read_only = False
    destructive = False
    function = user_sources.setup_user_source
