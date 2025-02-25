from baserow_premium.license.handler import LicenseHandler
from rest_framework import serializers

from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.types import WidgetDict
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.registries import WidgetType
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.features import CHART_WIDGET
from baserow_enterprise.integrations.local_baserow.service_types import (
    LocalBaserowGroupedAggregateRowsUserServiceType,
)

from .models import ChartWidget


class ChartWidgetType(WidgetType):
    type = "chart"
    model_class = ChartWidget
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

    class SerializedDict(WidgetDict):
        data_source_id: int

    def before_create(self, dashboard):
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            CHART_WIDGET, dashboard.workspace
        )

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
                    LocalBaserowGroupedAggregateRowsUserServiceType.type
                ),
            )
            values["data_source"] = data_source
        return values

    def before_trashed(self, instance: Widget):
        instance.data_source.trashed = True
        instance.data_source.save()

    def before_restore(self, instance: Widget):
        instance.data_source.trashed = False
        instance.data_source.save()

    def after_delete(self, instance: Widget):
        DashboardDataSourceHandler().delete_data_source(instance.data_source)

    def deserialize_property(
        self,
        prop_name: str,
        value: any,
        id_mapping: dict[str, any],
        **kwargs,
    ) -> any:
        if prop_name == "data_source_id" and value:
            return id_mapping["dashboard_data_sources"][value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            **kwargs,
        )

    def serialize_property(
        self,
        instance: Widget,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "data_source_id":
            return instance.data_source_id

        return super().serialize_property(
            instance,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
