from typing import Iterable

from django.contrib.auth.models import AbstractUser

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.operations import (
    ListDashboardDataSourcesOperationType,
    ReadDashboardDataSourceOperationType,
    UpdateDashboardDataSourceOperationType,
)
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
)
from baserow.contrib.integrations.local_baserow.service_filters.registries import (
    ServiceFilterTargetType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
)
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace


def _widget_titles(dashboard) -> dict[int, str]:
    """The title of the widget showing each data source of the dashboard."""

    return {
        widget.data_source_id: widget.title
        for widget in specific_iterator(Widget.objects.filter(dashboard=dashboard))
        if getattr(widget, "data_source_id", None)
    }


class DashboardDataSourceServiceFilterTargetType(ServiceFilterTargetType):
    type = "dashboard_data_source"
    application_type = "dashboard"
    read_operation_type = ReadDashboardDataSourceOperationType.type
    update_operation_type = UpdateDashboardDataSourceOperationType.type
    list_operation_type = ListDashboardDataSourcesOperationType.type
    # The widget filter form doesn't support filter groups.
    supports_filter_groups = False

    def get_owner(self, owner_id: int) -> DashboardDataSource:
        try:
            data_source = DashboardDataSourceHandler().get_data_source(owner_id)
        except DashboardDataSourceDoesNotExist as exc:
            raise ServiceFilterTargetDoesNotExist() from exc
        if data_source.dashboard.trashed:
            raise ServiceFilterTargetDoesNotExist()
        return data_source

    def get_workspace(self, owner: DashboardDataSource) -> Workspace:
        return owner.dashboard.workspace

    def get_name(self, owner: DashboardDataSource) -> str:
        # Data source names are generated, the widget title is what users know.
        titles = getattr(owner, "_widget_titles", None)
        if titles is None:
            titles = _widget_titles(owner.dashboard)
        return titles.get(owner.id) or owner.name

    def get_filters_unsupported_reason(self, owner, service) -> str | None:
        # The summary widget's form doesn't show filters, so they couldn't be seen
        # or removed there.
        if service.get_type().type == LocalBaserowAggregateRowsUserServiceType.type:
            return "Summary widgets don't have filters, only charts do."
        return None

    def get_location(self, owner: DashboardDataSource) -> str:
        return owner.dashboard.name

    def list_owners(
        self, user: AbstractUser, application
    ) -> Iterable[DashboardDataSource]:
        titles = _widget_titles(application)
        data_sources = CoreHandler().filter_queryset(
            user,
            self.list_operation_type,
            DashboardDataSource.objects.filter(dashboard=application).select_related(
                "dashboard", "service"
            ),
            workspace=application.workspace,
        )
        for data_source in data_sources:
            data_source._widget_titles = titles
            yield data_source

    def persist(self, user, owner, service_type, values) -> None:
        UpdateDashboardDataSourceActionType.do(user, owner.id, service_type, values)
