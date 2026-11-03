from baserow.contrib.dashboard.tools import widgets
from baserow.core.mcp.groups import (
    GROUP_DASHBOARD_DELETE,
    GROUP_DASHBOARD_EDIT,
    GROUP_DASHBOARD_READ,
)
from baserow.core.mcp.registries import FunctionMCPTool


class ListWidgetsMcpTool(FunctionMCPTool):
    type = "list_widgets"
    group = GROUP_DASHBOARD_READ
    title = "List widgets"
    read_only = True
    function = widgets.list_widgets


class GetWidgetDataMcpTool(FunctionMCPTool):
    type = "get_widget_data"
    group = GROUP_DASHBOARD_READ
    title = "Get widget data"
    read_only = True
    function = widgets.get_widget_data


class CreateWidgetsMcpTool(FunctionMCPTool):
    type = "create_widgets"
    group = GROUP_DASHBOARD_EDIT
    title = "Create widgets"
    read_only = False
    destructive = False
    function = widgets.create_widgets


class UpdateWidgetsMcpTool(FunctionMCPTool):
    type = "update_widgets"
    group = GROUP_DASHBOARD_EDIT
    title = "Update widgets"
    read_only = False
    destructive = True
    function = widgets.update_widgets


class DeleteWidgetsMcpTool(FunctionMCPTool):
    type = "delete_widgets"
    group = GROUP_DASHBOARD_DELETE
    title = "Delete widgets"
    read_only = False
    destructive = True
    function = widgets.delete_widgets
