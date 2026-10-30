from baserow.contrib.dashboard.operations import DashboardOperationType
from baserow.core.registries import OperationType


class CreateDashboardFilterOperationType(DashboardOperationType):
    type = "dashboard.create_filter"


class OrderDashboardFiltersOperationType(DashboardOperationType):
    type = "dashboard.order_filters"


class ListDashboardFiltersOperationType(DashboardOperationType):
    type = "dashboard.list_filters"
    object_scope_name = "dashboard_filter"


class ReadDashboardFilterOperationType(OperationType):
    type = "dashboard.filter.read"
    context_scope_name = "dashboard_filter"


class UpdateDashboardFilterOperationType(OperationType):
    type = "dashboard.filter.update"
    context_scope_name = "dashboard_filter"


class DeleteDashboardFilterOperationType(OperationType):
    type = "dashboard.filter.delete"
    context_scope_name = "dashboard_filter"


class RestoreDashboardFilterOperationType(OperationType):
    type = "dashboard.filter.restore"
    context_scope_name = "dashboard_filter"
