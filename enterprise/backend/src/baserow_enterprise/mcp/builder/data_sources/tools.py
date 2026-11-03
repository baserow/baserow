from baserow.core.mcp.groups import GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import data_sources


class ListDataSourcesMcpTool(FunctionMCPTool):
    type = "list_data_sources"
    group = GROUP_BUILDER_READ
    title = "List data sources"
    read_only = True
    function = data_sources.list_data_sources
