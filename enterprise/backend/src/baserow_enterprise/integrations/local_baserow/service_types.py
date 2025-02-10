from typing import TYPE_CHECKING, Type

from django.conf import settings
from django.db.models import OrderBy, QuerySet

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.database.fields.registries import field_aggregation_registry
from baserow.contrib.database.views.exceptions import AggregationTypeDoesNotExist
from baserow.contrib.database.views.utils import AnnotatedAggregation
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSortableMixin,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceSort,
    Service,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowViewServiceType,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import ServiceImproperlyConfigured
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import ServiceSortDictSubClass
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

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel


class LocalBaserowGroupedAggregateRowsUserServiceType(
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSortableMixin,
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
    serializer_mixins = (
        LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins
        + LocalBaserowTableServiceSortableMixin.mixin_serializer_mixins
    )

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
        )

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_names
            + LocalBaserowTableServiceSortableMixin.mixin_serializer_field_names
        ) + ["aggregation_series", "aggregation_group_bys"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            **LocalBaserowTableServiceSortableMixin.mixin_serializer_field_overrides,
            "aggregation_series": LocalBaserowTableServiceAggregationSeriesSerializer(
                many=True, source="service_aggregation_series", required=False
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
                if (
                    len(aggregation_series)
                    > settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_SERIES
                ):
                    raise DRFValidationError(
                        detail=f"The number of series exceeds the maximum allowed length of {settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_SERIES}.",
                        code="max_length_exceeded",
                    )
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
            table_field_ids = service.table.field_set.values_list("id", flat=True)

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
                if len(group_bys) > 1:
                    raise DRFValidationError(
                        detail=f"The number of group by fields exceeds the maximum allowed length of 1.",
                        code="max_length_exceeded",
                    )
                LocalBaserowTableServiceAggregationGroupBy.objects.bulk_create(
                    [
                        LocalBaserowTableServiceAggregationGroupBy(
                            **group_by, service=service, order=index
                        )
                        for index, group_by in enumerate(group_bys)
                        if validate_agg_group_by(group_by)
                    ]
                )

    def _update_service_sortings(
        self,
        service: LocalBaserowGroupedAggregateRows,
        service_sorts: list[ServiceSortDictSubClass] | None = None,
    ):
        with atomic_if_not_already():
            service.service_sorts.all().delete()
            if service_sorts is not None:
                table_field_ids = service.table.field_set.values_list("id", flat=True)
                model = service.table.get_model()

                allowed_sort_field_ids = [
                    series.field_id
                    for series in service.service_aggregation_series.all()
                ]

                if service.service_aggregation_group_bys.count() > 0:
                    group_by = service.service_aggregation_group_bys.all()[0]
                    allowed_sort_field_ids += (
                        [group_by.field_id]
                        if group_by.field_id is not None
                        else [model.get_primary_field().id]
                    )

                def validate_sort(service_sort):
                    if service_sort["field"].id not in table_field_ids:
                        raise DRFValidationError(
                            detail=f"The field with ID {service_sort['field'].id} is not "
                            "related to the given table.",
                            code="invalid_field",
                        )
                    if service_sort["field"].id not in allowed_sort_field_ids:
                        raise DRFValidationError(
                            detail=f"The field with ID {service_sort['field'].id} cannot be used for sorting.",
                            code="invalid_field",
                        )

                    return True

                LocalBaserowTableServiceSort.objects.bulk_create(
                    [
                        LocalBaserowTableServiceSort(
                            **service_sort, service=service, order=index
                        )
                        for index, service_sort in enumerate(service_sorts)
                        if validate_sort(service_sort)
                    ]
                )

    def after_create(self, instance: LocalBaserowGroupedAggregateRows, values: dict):
        """
        Responsible for creating service aggregation series and group bys.

        :param instance: The created service instance.
        :param values: The values that were passed when creating the service
            metadata.
        """

        if "service_aggregation_series" in values:
            self._update_service_aggregation_series(
                instance, values.pop("service_aggregation_series")
            )
        if "service_aggregation_group_bys" in values:
            self._update_service_aggregation_group_bys(
                instance, values.pop("service_aggregation_group_bys")
            )
        if "service_sorts" in values:
            self._update_service_sortings(instance, values.pop("service_sorts"))

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

        if "service_aggregation_series" in values:
            self._update_service_aggregation_series(
                instance, values.pop("service_aggregation_series")
            )
        elif from_table and to_table:
            instance.service_aggregation_series.all().delete()

        if "service_aggregation_group_bys" in values:
            self._update_service_aggregation_group_bys(
                instance, values.pop("service_aggregation_group_bys")
            )
        elif from_table and to_table:
            instance.service_aggregation_group_bys.all().delete()

        if "service_sorts" in values:
            self._update_service_sortings(instance, values.pop("service_sorts"))
        elif from_table and to_table:
            instance.service_sorts.all().delete()

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

    def get_dispatch_sorts(
        self,
        service: LocalBaserowGroupedAggregateRows,
        queryset: QuerySet,
        model: Type["GeneratedTableModel"],
    ) -> tuple[list[OrderBy], QuerySet]:
        service_sorts = service.service_sorts.all()
        sort_ordering = [service_sort.get_order_by() for service_sort in service_sorts]
        return sort_ordering, queryset

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

        allowed_sort_field_ids = [
            series.field_id for series in service.service_aggregation_series.all()
        ]

        if service.service_aggregation_group_bys.count() > 0:
            group_by = service.service_aggregation_group_bys.all()[0]
            allowed_sort_field_ids += (
                [group_by.field_id]
                if group_by.field_id is not None
                else [model.get_primary_field().id]
            )

        for sort_by in service.service_sorts.all():
            if sort_by.field_id not in allowed_sort_field_ids:
                raise ServiceImproperlyConfigured(
                    f"The field with ID {sort_by.field.id} cannot be used for sorting."
                )

        group_by_values = []
        for group_by in service.service_aggregation_group_bys.all():
            if group_by.field is None:
                group_by_values.append("id")
                group_by_values.append(model.get_primary_field().db_column)
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
            queryset = queryset.annotate(**combined_agg_dict)[
                : settings.BASEROW_ENTERPRISE_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS
            ]
            results = [process_individual_result(result) for result in queryset]
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
