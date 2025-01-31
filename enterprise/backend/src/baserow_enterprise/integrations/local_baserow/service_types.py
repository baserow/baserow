from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.database.fields.registries import field_aggregation_registry
from baserow.contrib.database.views.exceptions import AggregationTypeDoesNotExist
from baserow.contrib.database.views.utils import AnnotatedAggregation
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
)
from baserow.contrib.integrations.local_baserow.models import Service
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowViewServiceType,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import ServiceImproperlyConfigured
from baserow.core.services.registries import DispatchTypes
from baserow.core.utils import atomic_if_not_already
from baserow_enterprise.api.integrations.local_baserow.serializers import (
    LocalBaserowTableServiceAggregationGroupBySerializer,
    LocalBaserowTableServiceAggregationSeriesSerializer,
)
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)
from baserow_enterprise.services.types import (
    ServiceAggregationGroupByDict,
    ServiceAggregationSeriesDict,
)

from .models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


class LocalBaserowGroupedAggregateRowsUserServiceType(
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to multiple grouped aggregations over
    fields in a Baserow table or view.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_grouped_aggregate_rows"
    model_class = LocalBaserowGroupedAggregateRows
    dispatch_type = DispatchTypes.DISPATCH_DATA_SOURCE

    def get_schema_name(self, service: LocalBaserowGroupedAggregateRows) -> str:
        return f"GroupedAggregation{service.id}Schema"

    def get_context_data_schema(
        self, service: LocalBaserowGroupedAggregateRows
    ) -> dict | None:
        return None

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                "service_aggregation_series", "service_aggregation_group_bys"
            )
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + LocalBaserowTableServiceFilterableMixin.mixin_allowed_fields
            + [
                "service_aggregation_series",
                "service_aggregation_group_bys",
            ]
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
        ) + ["aggregation_series", "aggregation_group_bys"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            "aggregation_series": LocalBaserowTableServiceAggregationSeriesSerializer(
                many=True, source="service_aggregation_series", required=True
            ),
            "aggregation_group_bys": LocalBaserowTableServiceAggregationGroupBySerializer(
                many=True, source="service_aggregation_group_bys", required=False
            ),
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
    ):
        service_aggregation_series: list[ServiceAggregationSeriesDict]
        service_aggregation_group_bys: list[ServiceAggregationGroupByDict]

    def _update_service_aggregation_series(
        self,
        service: LocalBaserowGroupedAggregateRows,
        aggregation_series: list[ServiceAggregationSeriesDict] | None = None,
    ):
        with atomic_if_not_already():
            table_fields = service.table.field_set.all()
            table_field_ids = [field.id for field in table_fields]

            def validate_agg_series(agg_series):
                if agg_series["field_id"] not in table_field_ids:
                    raise DRFValidationError(
                        detail=f"The field with ID {agg_series['field_id']} is not "
                        "related to the given table.",
                        code="invalid_field",
                    )

                try:
                    agg_type = field_aggregation_registry.get(
                        agg_series["aggregation_type"]
                    )
                except AggregationTypeDoesNotExist:
                    raise DRFValidationError(
                        detail=f"The aggregation type '{agg_series['aggregation_type']}' "
                        f"doesn't exist",
                        code="invalid_aggregation_raw_type",
                    )
                field = next(
                    (
                        field
                        for field in table_fields
                        if field.id == agg_series["field_id"]
                    )
                )
                if not agg_type.field_is_compatible(field):
                    raise DRFValidationError(
                        detail=f"The field with ID {agg_series['field_id']} is not compatible "
                        f"with aggregation type {agg_series['aggregation_type']}.",
                        code="invalid_aggregation_raw_type",
                    )

                return True

            service.service_aggregation_series.all().delete()
            if aggregation_series is not None:
                LocalBaserowTableServiceAggregationSeries.objects.bulk_create(
                    [
                        LocalBaserowTableServiceAggregationSeries(
                            **agg_series, service=service, order=index
                        )
                        for index, agg_series in enumerate(aggregation_series)
                        if validate_agg_series(agg_series)
                    ]
                )

    def _update_service_aggregation_group_bys(
        self,
        service: LocalBaserowGroupedAggregateRows,
        group_bys: list[ServiceAggregationGroupByDict] | None = None,
    ):
        with atomic_if_not_already():
            table_fields = service.table.field_set.all()
            table_field_ids = [field.id for field in table_fields]

            def validate_agg_group_by(group_by):
                if group_by["field_id"] not in table_field_ids:
                    raise DRFValidationError(
                        detail=f"The field with ID {group_by['field_id']} is not "
                        "related to the given table.",
                        code="invalid_field",
                    )

                return True

            service.service_aggregation_group_bys.all().delete()
            if group_bys is not None:
                LocalBaserowTableServiceAggregationGroupBy.objects.bulk_create(
                    [
                        LocalBaserowTableServiceAggregationGroupBy(
                            **group_by, service=service, order=index
                        )
                        for index, group_by in enumerate(group_bys)
                        if validate_agg_group_by(group_by)
                    ]
                )

    def after_create(self, instance: LocalBaserowGroupedAggregateRows, values: dict):
        """
        Responsible for creating service aggregation series and group bys.

        :param instance: The created service instance.
        :param values: The values that were passed when creating the service
            metadata.
        """

        if "aggregation_series" in values:
            self._update_service_aggregation_series(
                instance, values.pop("aggregation_series")
            )
        if "aggregation_group_bys" in values:
            self._update_service_aggregation_group_bys(
                instance, values.pop("aggregation_group_bys")
            )

    def after_update(
        self,
        instance: LocalBaserowGroupedAggregateRows,
        values: dict,
        changes: dict[str, tuple],
    ) -> None:
        """
        Responsible for updating service aggregation series and group bys.
        At the moment all objects are recreated on update.

        :param instance: The service that was updated.
        :param values: A dictionary which may contain aggregation series and
            group bys.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        # Following a Table change, from one Table to another, we drop all
        # the things that are no longer applicable for the other table.
        from_table, to_table = changes.get("table", (None, None))

        if "aggregation_series" in values:
            self._update_service_aggregation_series(
                instance, values.pop("aggregation_series")
            )
        elif from_table and to_table:
            instance.service_aggregation_series.all().delete()

        if "aggregation_group_bys" in values:
            self._update_service_aggregation_group_bys(
                instance, values.pop("aggregation_group_bys")
            )
        elif from_table and to_table:
            instance.service_aggregation_group_bys.all().delete()

    def export_prepared_values(self, instance: Service) -> dict[str, any]:
        values = super().export_prepared_values(instance)

        # FIXME: for "service_aggregation_series", "service_aggregation_group_bys"

        return values

    def serialize_property(
        self,
        service: Service,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "filters":
            return self.serialize_filters(service)

        # FIXME: aggregation_series, aggregation_group_bys

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: any,
        id_mapping: dict[str, any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        if prop_name == "filters":
            return self.deserialize_filters(value, id_mapping)

        # FIXME: aggregation_series, aggregation_group_bys

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def dispatch_data(
        self,
        service: LocalBaserowGroupedAggregateRows,
        resolved_values: dict[str, any],
        dispatch_context: DispatchContext,
    ) -> dict[str, any]:
        """
        Returns aggregated results based on service series and group bys.

        :param service: The service that we are dispatching.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: The context used for the dispatch.
        :return: Aggregation results.
        """

        table = resolved_values["table"]
        model = self.get_table_model(service)
        queryset = self.build_queryset(service, table, dispatch_context, model=model)

        group_by_values = []
        for group_by in service.service_aggregation_group_bys.all():
            if group_by.field is None:
                group_by_values.append("id")
                break
            if group_by.field.trashed:
                raise ServiceImproperlyConfigured(
                    f"The field with ID {group_by.field.id} is trashed."
                )
            group_by_values.append(group_by.field.db_column)

        if len(group_by_values) > 0:
            queryset = queryset.values(*group_by_values)

        combined_agg_dict = {}
        defined_agg_series = service.service_aggregation_series.all()
        if len(defined_agg_series) == 0:
            raise ServiceImproperlyConfigured(
                f"There are no aggregation series defined."
            )
        for agg_series in defined_agg_series:
            if agg_series.field.trashed:
                raise ServiceImproperlyConfigured(
                    f"The field with ID {agg_series.field.id} is trashed."
                )
            model_field = model._meta.get_field(agg_series.field.db_column)
            try:
                agg_type = field_aggregation_registry.get(agg_series.aggregation_type)
            except AggregationTypeDoesNotExist as ex:
                raise ServiceImproperlyConfigured(
                    f"The the aggregation type {agg_series.aggregation_type} doesn't exist."
                ) from ex
            if not agg_type.field_is_compatible(agg_series.field):
                raise ServiceImproperlyConfigured(
                    f"The field with ID {agg_series.field.id} is not compatible "
                    f"with the aggregation type {agg_series.aggregation_type}."
                )

            combined_agg_dict |= agg_type._get_aggregation_dict(
                queryset, model_field, agg_series.field
            )

        for key, value in combined_agg_dict.items():
            if isinstance(value, AnnotatedAggregation):
                queryset = queryset.annotate(**value.annotations)
                combined_agg_dict[key] = value.aggregation

        def process_individual_result(result: dict):
            for agg_series in defined_agg_series:
                raw_value = result.pop(f"{agg_series.field.db_column}_raw")
                agg_type = field_aggregation_registry.get(agg_series.aggregation_type)
                result[
                    f"{agg_series.field.db_column}"
                ] = agg_type._compute_final_aggregation(
                    raw_value, result.get("total", None)
                )
            if "total" in result:
                del result["total"]
            return result

        if len(group_by_values) > 0:
            results = list(queryset.annotate(**combined_agg_dict))
            results = [process_individual_result(result) for result in results]
        else:
            results = queryset.aggregate(**combined_agg_dict)
            results = process_individual_result(results)

        return {
            "data": {"result": results},
            "baserow_table_model": model,
        }

    def dispatch_transform(
        self,
        data: any,
    ) -> any:
        return data["data"]
