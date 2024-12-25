from abc import ABC

from baserow.contrib.dashboard.operations import DashboardOperationType
from baserow.core.registries import OperationType


class ListDashboardDataSourcesOperationType(DashboardOperationType):
    type = "dashboard.list_data_sources"
    object_scope_name = "dashboard_data_source"


class CreateDashboardDataSourceOperationType(DashboardOperationType):
    type = "dashboard.create_data_source"


class DashboardDataSourceOperationType(OperationType, ABC):
    context_scope_name = "dashboard_data_source"


class DeleteDashboardDataSourceOperationType(DashboardDataSourceOperationType):
    type = "dashboard.data_source.delete"


class UpdateDashboardDataSourceOperationType(DashboardDataSourceOperationType):
    type = "dashboard.data_source.update"


class ReadDashboardDataSourceOperationType(DashboardDataSourceOperationType):
    type = "dashboard.data_source.read"


class DispatchDashboardDataSourceOperationType(DashboardDataSourceOperationType):
    type = "dashboard.data_source.dispatch"
