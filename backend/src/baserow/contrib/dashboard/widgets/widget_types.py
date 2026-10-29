from typing import Any

from rest_framework import serializers

from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.types import WidgetDict
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
)
from baserow.core.services.registries import service_type_registry

from .mixins import DisplayWidgetTypeMixin, FilterWidgetTypeMixin
from .models import SummaryWidget, TextFilterWidget
from .registries import WidgetType
from .types import WidgetGridLayout


class SummaryWidgetType(DisplayWidgetTypeMixin, WidgetType):
    type = "summary"
    model_class = SummaryWidget
    grid_layout = WidgetGridLayout(
        default_width=2,
        default_height=4,
        min_width=1,
        min_height=4,
        max_width=6,
        max_height=6,
    )
    serializer_field_names = ["data_source_id"]
    serializer_field_overrides = {
        "data_source_id": serializers.PrimaryKeyRelatedField(
            queryset=DashboardDataSource.objects.all(),
            required=False,
            default=None,
            help_text="References a data source field for the widget.",
        ),
    }
    request_serializer_field_names = []
    request_serializer_field_overrides = {}

    class SerializedDict(WidgetDict):
        data_source_id: int

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

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: dict[str, Any],
        **kwargs,
    ) -> Any:
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
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "data_source_id":
            return instance.data_source_id

        return super().serialize_property(
            instance,
            prop_name,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )


class TextFilterWidgetType(FilterWidgetTypeMixin, WidgetType):
    type = "text_filter"
    model_class = TextFilterWidget
    allowed_fields = [
        *WidgetType.allowed_fields,
        "placeholder",
        "default_value",
        "target_filters",
    ]
    serializer_field_names = ["placeholder", "default_value", "target_filters"]
    public_serializer_field_names = [
        "placeholder",
        "default_value",
        *FilterWidgetTypeMixin.public_serializer_field_names,
    ]
    grid_layout = WidgetGridLayout(
        default_width=2,
        default_height=4,
        min_width=1,
        min_height=4,
        max_width=6,
        max_height=6,
    )

    class SerializedDict(WidgetDict):
        placeholder: str
        default_value: str
        target_filters: list

    def get_filter_value(self, widget, values):
        return values.get(str(widget.id), widget.default_value)

    def validate_filter_value(self, widget, value):
        if not isinstance(value, str):
            raise serializers.ValidationError("Expected a string filter value.")
        return value
