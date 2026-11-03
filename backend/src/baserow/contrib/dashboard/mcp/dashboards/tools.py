from baserow.contrib.dashboard.tools import dashboards
from baserow.core.mcp.groups import GROUP_DASHBOARD_EDIT, GROUP_DASHBOARD_READ
from baserow.core.mcp.registries import FunctionMCPTool


class ListDashboardsMcpTool(FunctionMCPTool):
    type = "list_dashboards"
    group = GROUP_DASHBOARD_READ
    title = "List dashboards"
    read_only = True
    function = dashboards.list_dashboards


class CreateDashboardsMcpTool(FunctionMCPTool):
    type = "create_dashboards"
    group = GROUP_DASHBOARD_EDIT
    title = "Create dashboards"
    read_only = False
    destructive = False
    function = dashboards.create_dashboards
