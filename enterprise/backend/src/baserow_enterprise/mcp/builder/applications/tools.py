from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool
from baserow_enterprise.builder.tools import applications


class ListBuildersMcpTool(FunctionMCPTool):
    type = "list_builders"
    group = GROUP_BUILDER_READ
    title = "List application builders"
    read_only = True
    function = applications.list_builders


class CreateBuildersMcpTool(FunctionMCPTool):
    type = "create_builders"
    group = GROUP_BUILDER_EDIT
    title = "Create application builders"
    read_only = False
    destructive = False
    function = applications.create_builders


class UpdateBuilderMcpTool(FunctionMCPTool):
    type = "update_builder"
    group = GROUP_BUILDER_EDIT
    title = "Update an application builder"
    read_only = False
    destructive = False
    function = applications.update_builder
