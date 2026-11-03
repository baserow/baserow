from baserow.contrib.dashboard.tools import dashboards
from baserow.core.mcp.groups import GROUP_DASHBOARD_EDIT, GROUP_DASHBOARD_READ
from baserow.core.mcp.registries import FunctionMCPTool


class ListDashboardsMcpTool(FunctionMCPTool):
    type = "list_dashboards"
    group = GROUP_DASHBOARD_READ
    title = "List dashboards"
    read_only = True
    function = dashboards.list_dashboards


class CreateDashboardMcpTool(FunctionMCPTool):
    type = "create_dashboard"
    group = GROUP_DASHBOARD_EDIT
    title = "Create a dashboard"
    read_only = False
    destructive = False
    function = dashboards.create_dashboard


class UpdateDashboardMcpTool(FunctionMCPTool):
    type = "update_dashboard"
    group = GROUP_DASHBOARD_EDIT
    title = "Rename a dashboard"
    read_only = False
    destructive = False
    function = dashboards.update_dashboard
