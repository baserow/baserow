from django.db import transaction

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler

from .handler import DashboardFilterHandler
from .operations import (
    CreateDashboardFilterOperationType,
    DeleteDashboardFilterOperationType,
    ListDashboardFiltersOperationType,
    OrderDashboardFiltersOperationType,
    ReadDashboardFilterOperationType,
    UpdateDashboardFilterOperationType,
)
from .signals import dashboard_filters_updated


class DashboardFilterService:
    def __init__(self):
        self.handler = DashboardFilterHandler()

    def get_filter(self, user, filter_id):
        dashboard_filter = self.handler.get_filter(filter_id)
        CoreHandler().check_permissions(
            user,
            ReadDashboardFilterOperationType.type,
            workspace=dashboard_filter.dashboard.workspace,
            context=dashboard_filter,
        )
        return dashboard_filter

    def get_filters(self, user, dashboard_id):
        dashboard = DashboardHandler().get_dashboard(dashboard_id)
        CoreHandler().check_permissions(
            user,
            ListDashboardFiltersOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )
        return CoreHandler().filter_queryset(
            user,
            ListDashboardFiltersOperationType.type,
            self.handler.get_filters(dashboard),
            workspace=dashboard.workspace,
        )

    @transaction.atomic
    def create_filter(self, user, dashboard_id, **values):
        dashboard = DashboardHandler().get_dashboard_for_update(dashboard_id)
        CoreHandler().check_permissions(
            user,
            CreateDashboardFilterOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )
        dashboard_filter = self.handler.create_filter(dashboard, **values)
        dashboard_filters_updated.send(self, dashboard=dashboard, user=user)
        return dashboard_filter

    @transaction.atomic
    def order_filters(self, user, dashboard_id, order, ignore_missing=False):
        dashboard = DashboardHandler().get_dashboard_for_update(dashboard_id)
        CoreHandler().check_permissions(
            user,
            OrderDashboardFiltersOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )
        previous, ordered = self.handler.order_filters(
            dashboard, order, ignore_missing=ignore_missing
        )
        dashboard_filters_updated.send(
            self, dashboard=dashboard, user=user, order_only=True
        )
        return dashboard, previous, ordered

    @transaction.atomic
    def delete_filter(self, user, filter_id):
        dashboard_filter = self.handler.get_filter(filter_id, for_update=True)
        dashboard = dashboard_filter.dashboard
        CoreHandler().check_permissions(
            user,
            DeleteDashboardFilterOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard_filter,
        )
        TrashHandler.trash(user, dashboard.workspace, dashboard, dashboard_filter)
        dashboard_filters_updated.send(self, dashboard=dashboard, user=user)
        return dashboard_filter

    def restore_filter(self, user, filter_id):
        return TrashHandler.restore_item(user, "dashboard_filter", filter_id)

    @transaction.atomic
    def update_filter(self, user, filter_id, **values):
        dashboard_filter = self.handler.get_filter(filter_id)
        DashboardHandler().get_dashboard_for_update(dashboard_filter.dashboard_id)
        dashboard_filter = self.handler.get_filter(filter_id, for_update=True)
        CoreHandler().check_permissions(
            user,
            UpdateDashboardFilterOperationType.type,
            workspace=dashboard_filter.dashboard.workspace,
            context=dashboard_filter,
        )
        previous, updated = self.handler.update_filter(dashboard_filter, **values)
        dashboard_filters_updated.send(
            self, dashboard=dashboard_filter.dashboard, user=user
        )
        return dashboard_filter, previous, updated
