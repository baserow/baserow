from typing import cast

from django.db import IntegrityError
from django.db.models import QuerySet

from baserow_premium.api.dashboard.widgets.serializers import (
    ChartSeriesConfigSerializer,
    PieChartSeriesConfigSerializer,
)
from baserow_premium.dashboard.widgets.models import (
    ChartSeriesConfig,
    ChartWidget,
    PieChartSeriesConfig,
    PieChartWidget,
)
from baserow_premium.dashboard.widgets.types import SeriesConfig
from baserow_premium.integrations.local_baserow.service_types import (
    LocalBaserowGroupedAggregateRowsUserServiceType,
)
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from rest_framework import serializers

from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.types import WidgetDict
from baserow.contrib.dashboard.widgets.exceptions import WidgetImproperlyConfigured
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.registries import WidgetType
from baserow.contrib.dashboard.widgets.types import UpdatedWidget
from baserow.core.services.registries import service_type_registry


class ChartWidgetType(WidgetType):
    type = "chart"
    model_class = ChartWidget
    serializer_field_names = [
        "data_source_id",
        "series_config",
        "default_series_chart_type",
    ]
    serializer_field_overrides = {
        "data_source_id": serializers.PrimaryKeyRelatedField(
            queryset=DashboardDataSource.objects.all(),
            required=False,
            default=None,
            help_text="References a data source field for the widget.",
        ),
        "series_config": serializers.ListSerializer(
            child=ChartSeriesConfigSerializer(),
            required=False,
            help_text="Provides series configuration.",
        ),
    }
    request_serializer_field_names = ["series_config", "default_series_chart_type"]
    request_serializer_field_overrides = {
        "series_config": serializers.ListSerializer(
            child=ChartSeriesConfigSerializer(),
            required=False,
            help_text="Provides series configuration.",
        ),
    }

    class SerializedDict(WidgetDict):
        data_source_id: int
        series_config: list[SeriesConfig]
        default_series_chart_type: str

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["default_series_chart_type"]

    def enhance_queryset(self, queryset: QuerySet[Widget]) -> QuerySet[Widget]:
        return queryset.prefetch_related("series_config")

    def before_create(self, user, dashboard):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user, dashboard.workspace
        )

    def after_update(self, updated_widget: UpdatedWidget, **kwargs) -> UpdatedWidget:
        series_config = kwargs.get("series_config")
        if series_config is not None:
            allowed_series_ids = updated_widget.widget.data_source.service.service_aggregation_series.values_list(
                flat=True
            )
            existing_series_configs = ChartSeriesConfig.objects.filter(
                widget=updated_widget.widget
            )
            existing_series_configs_by_series_id = {
                series_conf.series_id: series_conf
                for series_conf in existing_series_configs
            }
            configs_to_create = []
            configs_to_update = []
            used_series_ids = set()

            for series_conf in series_config:
                if series_conf["series_id"] not in allowed_series_ids:
                    raise WidgetImproperlyConfigured(
                        "The series id cannot be used with the widget."
                    )
                if series_conf["series_id"] in used_series_ids:
                    raise WidgetImproperlyConfigured(
                        "The series id cannot be repeated in the configuration."
                    )

                if series_conf["series_id"] in existing_series_configs_by_series_id:
                    to_update = existing_series_configs_by_series_id.pop(
                        series_conf["series_id"]
                    )
                    to_update.series_chart_type = series_conf["series_chart_type"]
                    configs_to_update.append(to_update)
                    used_series_ids.add(series_conf["series_id"])
                else:
                    configs_to_create.append(
                        ChartSeriesConfig(
                            widget=updated_widget.widget,
                            series_id=series_conf["series_id"],
                            series_chart_type=series_conf["series_chart_type"],
                        )
                    )

            ChartSeriesConfig.objects.bulk_update(
                configs_to_update, fields=["series_chart_type"]
            )
            try:
                ChartSeriesConfig.objects.bulk_create(configs_to_create)
            except IntegrityError as ex:
                raise WidgetImproperlyConfigured(
                    "The series id cannot be repeated in the configuration."
                ) from ex

            ChartSeriesConfig.objects.filter(
                series_id__in=existing_series_configs_by_series_id.keys()
            ).delete()

            updated_widget.new_values["series_config"] = series_config
        return updated_widget

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

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> "ChartWidgetType":
        serialized_series_config = serialized_values.pop("series_config", [])
        chart = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        series_config_to_create = []
        for entry in serialized_series_config:
            entry["series_id"] = id_mapping["service_aggregation_series"][
                entry["series_id"]
            ]
            series_config_to_create.append(ChartSeriesConfig(**entry, widget=chart))

        ChartSeriesConfig.objects.bulk_create(series_config_to_create)

        return cast(ChartWidgetType, chart)

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

        if prop_name == "series_config":
            return [
                {
                    "series_id": conf.series_id,
                    "series_chart_type": conf.series_chart_type,
                }
                for conf in instance.series_config.all()
            ]

        return super().serialize_property(
            instance,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )


class PieChartWidgetType(WidgetType):
    type = "pie_chart"
    model_class = PieChartWidget
    serializer_field_names = [
        "data_source_id",
        "series_config",
        "default_series_chart_type",
    ]
    serializer_field_overrides = {
        "data_source_id": serializers.PrimaryKeyRelatedField(
            queryset=DashboardDataSource.objects.all(),
            required=False,
            default=None,
            help_text="References a data source field for the widget.",
        ),
        "series_config": serializers.ListSerializer(
            child=PieChartSeriesConfigSerializer(),
            required=False,
            help_text="Provides series configuration.",
        ),
    }
    request_serializer_field_names = ["series_config", "default_series_chart_type"]
    request_serializer_field_overrides = {
        "series_config": serializers.ListSerializer(
            child=PieChartSeriesConfigSerializer(),
            required=False,
            help_text="Provides series configuration.",
        ),
    }

    class SerializedDict(WidgetDict):
        data_source_id: int
        series_config: list[SeriesConfig]
        default_series_chart_type: str

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["default_series_chart_type"]

    def enhance_queryset(self, queryset: QuerySet[Widget]) -> QuerySet[Widget]:
        return queryset.prefetch_related("series_config")

    def before_create(self, user, dashboard):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user, dashboard.workspace
        )

    def after_update(self, updated_widget: UpdatedWidget, **kwargs) -> UpdatedWidget:
        series_config = kwargs.get("series_config")
        if series_config is not None:
            allowed_series_ids = updated_widget.widget.data_source.service.service_aggregation_series.values_list(
                flat=True
            )
            existing_series_configs = PieChartSeriesConfig.objects.filter(
                widget=updated_widget.widget
            )
            existing_series_configs_by_series_id = {
                series_conf.series_id: series_conf
                for series_conf in existing_series_configs
            }
            configs_to_create = []
            configs_to_update = []
            used_series_ids = set()

            for series_conf in series_config:
                if series_conf["series_id"] not in allowed_series_ids:
                    raise WidgetImproperlyConfigured(
                        "The series id cannot be used with the widget."
                    )
                if series_conf["series_id"] in used_series_ids:
                    raise WidgetImproperlyConfigured(
                        "The series id cannot be repeated in the configuration."
                    )

                if series_conf["series_id"] in existing_series_configs_by_series_id:
                    to_update = existing_series_configs_by_series_id.pop(
                        series_conf["series_id"]
                    )
                    to_update.series_chart_type = series_conf["series_chart_type"]
                    configs_to_update.append(to_update)
                    used_series_ids.add(series_conf["series_id"])
                else:
                    configs_to_create.append(
                        PieChartSeriesConfig(
                            widget=updated_widget.widget,
                            series_id=series_conf["series_id"],
                            series_chart_type=series_conf["series_chart_type"],
                        )
                    )

            PieChartSeriesConfig.objects.bulk_update(
                configs_to_update, fields=["series_chart_type"]
            )
            try:
                PieChartSeriesConfig.objects.bulk_create(configs_to_create)
            except IntegrityError as ex:
                raise WidgetImproperlyConfigured(
                    "The series id cannot be repeated in the configuration."
                ) from ex

            PieChartSeriesConfig.objects.filter(
                series_id__in=existing_series_configs_by_series_id.keys()
            ).delete()

            updated_widget.new_values["series_config"] = series_config
        return updated_widget

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

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> "PieChartWidgetType":
        serialized_series_config = serialized_values.pop("series_config", [])
        chart = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        series_config_to_create = []
        for entry in serialized_series_config:
            entry["series_id"] = id_mapping["service_aggregation_series"][
                entry["series_id"]
            ]
            series_config_to_create.append(PieChartSeriesConfig(**entry, widget=chart))

        PieChartSeriesConfig.objects.bulk_create(series_config_to_create)

        return cast(PieChartWidgetType, chart)

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

        if prop_name == "series_config":
            return [
                {
                    "series_id": conf.series_id,
                    "series_chart_type": conf.series_chart_type,
                }
                for conf in instance.series_config.all()
            ]

        return super().serialize_property(
            instance,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
