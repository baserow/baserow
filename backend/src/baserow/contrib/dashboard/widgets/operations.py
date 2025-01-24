from abc import ABC

from baserow.contrib.dashboard.operations import DashboardOperationType


class WidgetOperationType(DashboardOperationType, ABC):
    context_scope_name = "dashboard_widget"


class CreateWidgetOperationType(DashboardOperationType):
    type = "dashboard.create_widget"


class ReadWidgetOperationType(WidgetOperationType):
    type = "dashboard.widget.read"


class UpdateWidgetOperationType(WidgetOperationType):
    type = "dashboard.widget.update"


class DeleteWidgetOperationType(WidgetOperationType):
    type = "dashboard.widget.delete"


class RestoreWidgetOperationType(WidgetOperationType):
    type = "dashboard.widget.restore"


class ListWidgetsOperationType(DashboardOperationType):
    type = "dashboard.list_widgets"
    object_scope_name = "dashboard_widget"
