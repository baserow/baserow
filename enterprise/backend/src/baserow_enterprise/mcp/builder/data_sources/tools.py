from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import data_sources


class ListDataSourcesMcpTool(FunctionMCPTool):
    type = "list_data_sources"
    group = GROUP_BUILDER_READ
    title = "List data sources"
    read_only = True
    function = data_sources.list_data_sources


class CreateDataSourcesMcpTool(FunctionMCPTool):
    type = "create_data_sources"
    group = GROUP_BUILDER_EDIT
    title = "Create data sources"
    read_only = False
    destructive = False
    function = data_sources.create_data_sources


class UpdateDataSourceMcpTool(FunctionMCPTool):
    type = "update_data_source"
    group = GROUP_BUILDER_EDIT
    title = "Update a data source"
    read_only = False
    destructive = True
    function = data_sources.update_data_source
