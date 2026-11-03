from baserow.contrib.database.tools import view_config, views
from baserow.core.mcp.groups import (
    GROUP_DATABASE_DELETE,
    GROUP_DATABASE_EDIT,
    GROUP_DATABASE_READ,
)
from baserow.core.mcp.registries import FunctionMCPTool


class ListViewsMcpTool(FunctionMCPTool):
    type = "list_views"
    group = GROUP_DATABASE_READ
    title = "List views"
    read_only = True
    function = views.list_views


class CreateViewsMcpTool(FunctionMCPTool):
    type = "create_views"
    group = GROUP_DATABASE_EDIT
    title = "Create views"
    read_only = False
    destructive = False
    function = views.create_views


class CreateViewFiltersMcpTool(FunctionMCPTool):
    type = "create_view_filters"
    group = GROUP_DATABASE_EDIT
    title = "Create view filters"
    read_only = False
    destructive = False
    function = views.create_view_filters


class SetViewSortsMcpTool(FunctionMCPTool):
    type = "set_view_sorts"
    group = GROUP_DATABASE_EDIT
    title = "Set view sorts"
    read_only = False
    destructive = True
    function = view_config.set_view_sorts


class SetFieldVisibilityMcpTool(FunctionMCPTool):
    type = "set_field_visibility"
    group = GROUP_DATABASE_EDIT
    title = "Hide or show fields"
    read_only = False
    destructive = False
    function = view_config.set_field_visibility


class SetRowColoursMcpTool(FunctionMCPTool):
    type = "set_row_colours"
    group = GROUP_DATABASE_EDIT
    title = "Set row colours"
    read_only = False
    destructive = False
    function = view_config.set_row_colours


class DeleteViewsMcpTool(FunctionMCPTool):
    type = "delete_views"
    group = GROUP_DATABASE_DELETE
    title = "Delete views"
    read_only = False
    destructive = True
    function = view_config.delete_views


class DeleteViewFiltersMcpTool(FunctionMCPTool):
    type = "delete_view_filters"
    group = GROUP_DATABASE_DELETE
    title = "Delete view filters"
    read_only = False
    destructive = True
    function = view_config.delete_view_filters


class DeleteRowColoursMcpTool(FunctionMCPTool):
    type = "delete_row_colours"
    group = GROUP_DATABASE_DELETE
    title = "Delete row colours"
    read_only = False
    destructive = True
    function = view_config.delete_row_colours
