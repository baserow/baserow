from baserow.contrib.integrations.local_baserow.service_filters import tools
from baserow.core.mcp.groups import GROUP_DATA_SOURCES_EDIT, GROUP_DATA_SOURCES_READ
from baserow.core.mcp.registries import FunctionMCPTool


class ListFilterableDataSourcesMcpTool(FunctionMCPTool):
    type = "list_filterable_data_sources"
    group = GROUP_DATA_SOURCES_READ
    title = "List filterable data sources"
    read_only = True
    function = tools.list_filterable_data_sources


class ListServiceFiltersMcpTool(FunctionMCPTool):
    type = "list_service_filters"
    group = GROUP_DATA_SOURCES_READ
    title = "List data source filters"
    read_only = True
    function = tools.list_service_filters


class UpdateServiceFiltersMcpTool(FunctionMCPTool):
    type = "update_service_filters"
    group = GROUP_DATA_SOURCES_EDIT
    title = "Update data source filters"
    read_only = False
    # It deletes filters too.
    destructive = True
    function = tools.update_service_filters
