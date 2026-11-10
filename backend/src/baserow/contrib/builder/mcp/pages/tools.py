from baserow.contrib.builder.tools import pages
from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import FunctionMCPTool


class ListPagesMcpTool(FunctionMCPTool):
    type = "list_pages"
    group = GROUP_BUILDER_READ
    title = "List pages"
    read_only = True
    function = pages.list_pages


class CreatePagesMcpTool(FunctionMCPTool):
    type = "create_pages"
    group = GROUP_BUILDER_EDIT
    title = "Create pages"
    read_only = False
    destructive = False
    function = pages.create_pages


class UpdatePageMcpTool(FunctionMCPTool):
    type = "update_page"
    group = GROUP_BUILDER_EDIT
    title = "Update a page"
    read_only = False
    destructive = True
    function = pages.update_page


class SetupPageMcpTool(FunctionMCPTool):
    type = "setup_page"
    group = GROUP_BUILDER_EDIT
    title = "Set up a page"
    read_only = False
    destructive = False
    function = pages.setup_page
