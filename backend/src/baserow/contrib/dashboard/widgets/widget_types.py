from rest_framework import serializers

from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
)
from baserow.core.services.registries import service_type_registry

from .models import SummaryWidget
from .registries import WidgetType


class SummaryWidgetType(WidgetType):
    type = "summary"
    model_class = SummaryWidget
    serializer_field_names = ["data_source_id"]
    serializer_field_overrides = {
        "data_source_id": serializers.PrimaryKeyRelatedField(
            queryset=DashboardDataSource.objects.all(),
            required=False,
            default=None,
            help_text="References a data source field for the widget.",
        )
    }
    request_serializer_field_names = []
    request_serializer_field_overrides = {}

    def prepare_value_for_db(self, values: dict, instance: Widget | None = None):
        if instance is None:
            # When the widget is being created we want to automatically
            # create a data source for it
            available_name = DashboardDataSourceHandler().find_unused_data_source_name(
                values["dashboard"], "WidgetDataSource"
            )
            data_source = DashboardDataSourceHandler().create_data_source(
                dashboard=values["dashboard"],
                name=available_name,
                service_type=service_type_registry.get(
                    LocalBaserowAggregateRowsUserServiceType.type
                ),
            )
            values["data_source"] = data_source
        return values

    def after_delete(self, instance: Widget):
        DashboardDataSourceHandler().delete_data_source(instance.data_source)
