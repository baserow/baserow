import re
from typing import Any

from django.conf import settings
from django.db.models import F

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.fields.exceptions import FieldTypeDoesNotExist
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.exceptions import AggregationTypeDoesNotExist
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY
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
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import (
    DispatchTypes,
    ListServiceTypeMixin,
    ServiceType,
)
from baserow.core.services.types import DispatchResult
from baserow.core.utils import atomic_if_not_already
from baserow_premium.api.integrations.local_baserow.serializers import (
    LocalBaserowTableServiceAggregationGroupBySerializer,
    LocalBaserowTableServiceAggregationSeriesSerializer,
    LocalBaserowTableServiceAggregationSortBySerializer,
)
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
    LocalBaserowTableServiceAggregationSortBy,
)
from baserow_premium.integrations.registries import (
    grouped_aggregation_group_by_registry,
    grouped_aggregation_registry,
)
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.services.types import (
    ServiceAggregationGroupByDict,
    ServiceAggregationSeriesDict,
    ServiceAggregationSortByDict,
)

BUILDER_GROUPED_AGGREGATE_ROWS = "builder_grouped_aggregate_rows"
GROUPED_AGGREGATE_ROW_ID = "id"


class LocalBaserowGroupedAggregateRowsUserServiceType(
    LocalBaserowTableServiceFilterableMixin,
    ListServiceTypeMixin,
    LocalBaserowViewServiceType,
):
    """
    This service gives access to multiple grouped aggregations over
    fields in a Baserow table or view.
    """

    integration_type = LocalBaserowIntegrationType.type
    type = "local_baserow_grouped_aggregate_rows"
    model_class = LocalBaserowGroupedAggregateRows
    dispatch_types = [DispatchTypes.DATA]
    serializer_mixins = LocalBaserowTableServiceFilterableMixin.mixin_serializer_mixins

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(
            BUILDER_GROUPED_AGGREGATE_ROWS, workspace
        )

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            BUILDER_GROUPED_AGGREGATE_ROWS, workspace
        )

    def dispatch(
        self,
        service: LocalBaserowGroupedAggregateRows,
        dispatch_context: DispatchContext,
    ) -> DispatchResult:
        self.raise_if_deactivated(dispatch_context.workspace)

        return super().dispatch(service, dispatch_context)

    def get_schema_name(self, service: LocalBaserowGroupedAggregateRows) -> str:
        return f"GroupedAggregation{service.id}Schema"

    def get_context_data_schema(
        self, service: LocalBaserowGroupedAggregateRows
    ) -> dict | None:
        return None

    def prepare_record_ids(self, record_ids: list[Any]) -> list[str]:
        return [str(record_id) for record_id in record_ids if record_id != ""]

    def get_id_property(self, service: Service) -> str:
        return GROUPED_AGGREGATE_ROW_ID

    def get_name_property(self, service: Service) -> str | None:
        group_by = service.service_aggregation_group_bys.first()
        if group_by is None:
            return None

        if group_by.field_id is None:
            return service.table.get_model().get_primary_field().db_column

        return group_by.field.db_column

    def _get_name_field_object(self, service: Service) -> dict | None:
        group_by = service.service_aggregation_group_bys.first()
        if group_by is None:
            return None

        field_id = group_by.field_id
        if field_id is None:
            field_id = service.table.get_model().get_primary_field().id

        for field_object in self.get_table_field_objects(service) or []:
            if field_object["field"].id == field_id:
                return field_object

        return None

    def _get_human_readable_result_value(
        self,
        value: Any,
        field_object: dict | None,
        model,
    ) -> str:
        if field_object is None:
            return ""
        if value == "OTHER_VALUES":
            return value

        model_field = model._meta.get_field(field_object["name"])
        related_model = getattr(model_field.remote_field, "model", None)
        if related_model is not None and value is not None:
            try:
                value = related_model.objects.get(pk=value)
            except (TypeError, ValueError, related_model.DoesNotExist):
                value = None

        human_readable_value = field_object["type"].get_human_readable_value(
            value, field_object
        )
        if human_readable_value is None:
            return ""

        return str(human_readable_value)

    def _get_result_record_id(
        self,
        service: LocalBaserowGroupedAggregateRows,
        result: dict,
        index: int,
        model,
    ) -> str:
        name_property = self.get_name_property(service)
        if name_property is None:
            return "Result"

        value = self._get_human_readable_result_value(
            result.get(name_property), self._get_name_field_object(service), model
        )

        if value is None or value == "":
            return str(index)

        return value

    def generate_schema(
        self,
        service: LocalBaserowGroupedAggregateRows,
        allowed_fields: list[str] | None = None,
    ) -> dict | None:
        if not service.table_id:
            return None

        result_properties = self._get_result_properties(service)
        if result_properties is None:
            return None

        if allowed_fields is not None:
            allowed_fields = set(allowed_fields)
            result_properties = {
                field: value
                for field, value in result_properties.items()
                if field in allowed_fields
            }

        return {
            "type": "array",
            "title": self.get_schema_name(service),
            "items": {
                "type": "object",
                "properties": result_properties,
            },
        }

    def _get_result_properties(
        self,
        service: LocalBaserowGroupedAggregateRows,
    ) -> dict | None:
        table_properties = self._get_table_properties(service)
        if table_properties is None:
            return None

        def grouped_field_property(field_db_column):
            return {
                **table_properties[field_db_column],
                "sortable": False,
                "filterable": False,
                "searchable": False,
            }

        properties = {
            GROUPED_AGGREGATE_ROW_ID: {
                "title": "Id",
                "type": "string",
                "sortable": False,
                "filterable": False,
                "searchable": False,
            },
        }
        group_bys = service.service_aggregation_group_bys.all()
        for group_by in group_bys:
            if group_by.field_id is None:
                primary_field = service.table.get_model().get_primary_field()
                properties[primary_field.db_column] = grouped_field_property(
                    primary_field.db_column
                )
            elif group_by.field.db_column in table_properties:
                properties[group_by.field.db_column] = grouped_field_property(
                    group_by.field.db_column
                )

        for aggregation_series in service.service_aggregation_series.all():
            if not aggregation_series.field or not aggregation_series.aggregation_type:
                continue
            aggregation_type = grouped_aggregation_registry.get(
                aggregation_series.aggregation_type
            )
            properties[
                f"{aggregation_series.field.db_column}_{aggregation_series.aggregation_type}"
            ] = {
                "title": (
                    f"{aggregation_series.field.name} "
                    f"{aggregation_series.aggregation_type}"
                ),
                **aggregation_type.get_result_schema(aggregation_series.field.specific),
                "metadata": self.get_aggregation_result_metadata(aggregation_series),
            }

        return properties

    def get_aggregation_result_metadata(
        self, aggregation_series: LocalBaserowTableServiceAggregationSeries
    ) -> dict:
        field = aggregation_series.field
        return {
            "display_name": f"{field.name} {aggregation_series.aggregation_type}",
            "source_field": {
                "id": field.id,
                "name": field.db_column,
                "display_name": field.name,
            },
            "aggregation": {
                "type": aggregation_series.aggregation_type,
            },
        }

    def prepare_value_path(self, service: Service, path: list[str]):
        if len(path) < 1:
            return path

        property_name, *rest = path
        human_name = self._get_result_property_human_name(service, property_name)
        if human_name == property_name:
            return path

        return [human_name, *rest]

    def _get_result_property_human_name(self, service: Service, property_name: str):
        if property_name == GROUPED_AGGREGATE_ROW_ID:
            return property_name

        result_properties = self._get_result_properties(service) or {}
        property_schema = result_properties.get(property_name)
        if property_schema is None:
            return property_name

        return (
            property_schema.get("metadata", {}).get("display_name")
            or property_schema.get("title")
            or property_name
        )

    def _convert_result_property_names_to_human_names(
        self, service: Service, result: dict
    ):
        return {
            self._get_result_property_human_name(service, key): value
            for key, value in result.items()
        }

    def _convert_allowed_field_names(self, service, allowed_fields):
        return [
            self._get_result_property_human_name(service, field)
            for field in allowed_fields
        ]

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                "service_aggregation_series",
                "service_aggregation_group_bys",
                "service_aggregation_sorts",
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
        ) + ["aggregation_series", "aggregation_group_bys", "aggregation_sorts"]

    @property
    def serializer_field_overrides(self):
        return {
            **super().serializer_field_overrides,
            **LocalBaserowTableServiceFilterableMixin.mixin_serializer_field_overrides,
            "aggregation_series": LocalBaserowTableServiceAggregationSeriesSerializer(
                many=True, source="service_aggregation_series", required=False
            ),
            "aggregation_group_bys": LocalBaserowTableServiceAggregationGroupBySerializer(
                many=True, source="service_aggregation_group_bys", required=False
            ),
            "aggregation_sorts": LocalBaserowTableServiceAggregationSortBySerializer(
                many=True, source="service_aggregation_sorts", required=False
            ),
        }

    class SerializedDict(
        LocalBaserowViewServiceType.SerializedDict,
        LocalBaserowTableServiceFilterableMixin.SerializedDict,
    ):
        service_aggregation_series: list[ServiceAggregationSeriesDict]
        service_aggregation_group_bys: list[ServiceAggregationGroupByDict]
        service_aggregation_sorts: list[ServiceAggregationSortByDict]

    def _update_service_aggregation_series(
        self,
        service: LocalBaserowGroupedAggregateRows,
        aggregation_series: list[ServiceAggregationSeriesDict] | None = None,
        id_mapping: dict | None = None,
    ):
        with atomic_if_not_already():
            table_fields = service.table.field_set.all()
            table_field_ids = [field.id for field in table_fields]
            series_agg_used = set()

            def validate_agg_series(agg_series):
                if agg_series["aggregation_type"]:
                    try:
                        agg_type = grouped_aggregation_registry.get(
                            agg_series["aggregation_type"]
                        )
                    except AggregationTypeDoesNotExist:
                        raise DRFValidationError(
                            detail=f"The aggregation type '{agg_series['aggregation_type']}' "
                            f"doesn't exist",
                            code="invalid_aggregation_raw_type",
                        )

                if agg_series["field_id"] is not None:
                    if agg_series["field_id"] not in table_field_ids:
                        raise DRFValidationError(
                            detail=f"The field with ID {agg_series['field_id']} is not "
                            "related to the given table.",
                            code="invalid_field",
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

                series_aggregation_reference = (
                    f"field_{agg_series['field_id']}_{agg_series['aggregation_type']}"
                )
                if series_aggregation_reference in series_agg_used:
                    raise DRFValidationError(
                        detail=f"The series with the field ID {agg_series['field_id']} and "
                        f"aggregation type {agg_series['aggregation_type']} can only be defined once.",
                        code="invalid_aggregation_raw_type",
                    )
                else:
                    # It is still possible to have multiple undefined series
                    if agg_series["field_id"] and agg_series["aggregation_type"]:
                        series_agg_used.add(series_aggregation_reference)

                return True

            if aggregation_series is not None:
                if (
                    len(aggregation_series)
                    > settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES
                ):
                    raise DRFValidationError(
                        detail=f"The number of series exceeds the maximum allowed length of {settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES}.",
                        code="max_length_exceeded",
                    )

                existing_series = service.service_aggregation_series.all()
                existing_series_by_id = {
                    series.id: series for series in existing_series
                }

                # If id_mapping is provided we assume that we are importing
                id_mapping_old_series_ids = []
                if id_mapping is not None:
                    if "service_aggregation_series" not in id_mapping:
                        id_mapping["service_aggregation_series"] = {}
                    id_mapping_old_series_ids = [
                        current_series.pop("id", None)
                        for current_series in aggregation_series
                    ]

                series_to_add = []
                series_to_update = []
                order = 1
                for agg_series in aggregation_series:
                    validate_agg_series(agg_series)

                    if "id" in agg_series:
                        if agg_series["id"] not in existing_series_by_id:
                            raise DRFValidationError(
                                detail=f"The series with id {agg_series['id']} does not exist.",
                                code="invalid_series",
                            )
                        to_update = existing_series_by_id.pop(agg_series["id"])
                        to_update.field_id = agg_series["field_id"]
                        to_update.aggregation_type = agg_series["aggregation_type"]
                        to_update.order = order
                        series_to_update.append(to_update)
                    else:
                        series_to_add.append(
                            LocalBaserowTableServiceAggregationSeries(
                                **agg_series, service=service, order=order
                            )
                        )
                    order += 1

                LocalBaserowTableServiceAggregationSeries.objects.bulk_update(
                    series_to_update,
                    fields=["field_id", "aggregation_type", "order"],
                )

                created_series = (
                    LocalBaserowTableServiceAggregationSeries.objects.bulk_create(
                        series_to_add
                    )
                )

                if id_mapping is not None:
                    for i in range(len(created_series)):
                        id_mapping["service_aggregation_series"][
                            id_mapping_old_series_ids[i]
                        ] = created_series[i].id

                service.service_aggregation_series.filter(
                    id__in=existing_series_by_id.keys()
                ).delete()

                service.refresh_from_db()

    def _update_service_aggregation_group_bys(
        self,
        service: LocalBaserowGroupedAggregateRows,
        group_bys: list[ServiceAggregationGroupByDict] | None = None,
    ):
        with atomic_if_not_already():
            table_fields = service.table.field_set.all()
            table_field_ids = [field.id for field in table_fields]

            def validate_agg_group_by(group_by):
                if (
                    group_by["field_id"] not in table_field_ids
                    and group_by["field_id"] is not None
                ):
                    raise DRFValidationError(
                        detail=f"The field with ID {group_by['field_id']} is not "
                        "related to the given table.",
                        code="invalid_field",
                    )

                if group_by["field_id"] is None:
                    return True

                field = next(
                    (
                        field
                        for field in table_fields
                        if field.id == group_by["field_id"]
                    )
                )

                try:
                    grouped_aggregation_group_by_registry.get_by_type(field.get_type())
                except FieldTypeDoesNotExist:
                    raise DRFValidationError(
                        detail=f"The field with ID {group_by['field_id']} cannot "
                        "be used as a group by field.",
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

    def _update_service_sorts(
        self,
        service: LocalBaserowGroupedAggregateRows,
        service_sorts: list[ServiceAggregationSortByDict] | None = None,
    ):
        with atomic_if_not_already():
            service.service_aggregation_sorts.all().delete()
            if service_sorts is not None:
                model = service.table.get_model()

                allowed_sort_references = [
                    f"field_{series.field_id}_{series.aggregation_type}"
                    for series in service.service_aggregation_series.all()
                    if series.aggregation_type is not None
                    and series.field_id is not None
                ]

                if service.service_aggregation_group_bys.count() > 0:
                    group_by = service.service_aggregation_group_bys.all()[0]
                    allowed_sort_references += (
                        [f"field_{group_by.field_id}"]
                        if group_by.field_id is not None
                        else [f"field_{model.get_primary_field().id}"]
                    )

                def validate_sort(service_sort):
                    if service_sort["reference"] not in allowed_sort_references:
                        raise DRFValidationError(
                            detail=f"The reference sort '{service_sort['reference']}' cannot be used for sorting.",
                            code="invalid",
                        )

                    return True

                LocalBaserowTableServiceAggregationSortBy.objects.bulk_create(
                    [
                        LocalBaserowTableServiceAggregationSortBy(
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

        super().after_create(instance, values)

        if "service_aggregation_series" in values:
            self._update_service_aggregation_series(
                instance, values.pop("service_aggregation_series")
            )
        if "service_aggregation_group_bys" in values:
            self._update_service_aggregation_group_bys(
                instance, values.pop("service_aggregation_group_bys")
            )
        if "service_aggregation_sorts" in values:
            self._update_service_sorts(
                instance, values.pop("service_aggregation_sorts")
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

        super().after_update(instance, values, changes)

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

        if "service_aggregation_sorts" in values:
            self._update_service_sorts(
                instance, values.pop("service_aggregation_sorts")
            )
        elif from_table and to_table:
            instance.service_aggregation_sorts.all().delete()

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

        if prop_name == "service_aggregation_series":
            return [
                {
                    "id": series.id,
                    "field_id": series.field_id,
                    "aggregation_type": series.aggregation_type,
                }
                for series in service.service_aggregation_series.all()
            ]

        if prop_name == "service_aggregation_group_bys":
            return [
                {
                    "field_id": group_by.field_id,
                }
                for group_by in service.service_aggregation_group_bys.all()
            ]

        if prop_name == "service_aggregation_sorts":
            return [
                {
                    "sort_on": sort.sort_on,
                    "reference": sort.reference,
                    "direction": sort.direction,
                }
                for sort in service.service_aggregation_sorts.all()
            ]

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> "LocalBaserowGroupedAggregateRowsUserServiceType":
        series = serialized_values.pop("service_aggregation_series", [])
        group_bys = serialized_values.pop("service_aggregation_group_bys", [])
        sorts = serialized_values.pop("service_aggregation_sorts", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        if "database_fields" in id_mapping:
            for current_series in series:
                if current_series["field_id"] is not None:
                    current_series["field_id"] = id_mapping["database_fields"].get(
                        current_series["field_id"], None
                    )
            for group_by in group_bys:
                if group_by["field_id"] is not None:
                    group_by["field_id"] = id_mapping["database_fields"].get(
                        group_by["field_id"], None
                    )
            for sort in sorts:
                match = re.search(r"\d+", sort["reference"])
                sort_field_id = match.group()
                remapped_id = id_mapping["database_fields"].get(
                    int(sort_field_id), None
                )
                if remapped_id is not None:
                    sort["reference"] = sort["reference"].replace(
                        sort_field_id, str(remapped_id)
                    )
                else:
                    sort["reference"] = None

        if service.table_id is not None:
            self._update_service_aggregation_series(service, series, id_mapping)
            self._update_service_aggregation_group_bys(service, group_bys)
            self._update_service_sorts(
                service, [sort for sort in sorts if sort["reference"] is not None]
            )

        return service

    def get_context_data(
        self,
        service: LocalBaserowGroupedAggregateRows,
        allowed_fields: list[str] | None = None,
    ) -> dict:
        context_data = {}

        if service.table:
            model = service.table.get_model()

            def get_group_by_field(field):
                return model.get_primary_field() if field is None else field

            def serialize_field(field):
                return field_type_registry.get_serializer(field, FieldSerializer).data

            fields = [
                get_group_by_field(group_by.field)
                for group_by in service.service_aggregation_group_bys.all()
            ]
            context_data["fields"] = {
                field.db_column: serialize_field(field) for field in fields
            }

        return context_data

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

        table = service.table
        model = self.get_table_model(service)
        queryset = self.build_queryset(service, table, dispatch_context, model=model)
        other_buckets_qs = queryset.all()

        group_by_values = []
        for group_by in service.service_aggregation_group_bys.all():
            if group_by.field is None:
                group_by_values.append("id")
                group_by_values.append(model.get_primary_field().db_column)
                break
            if group_by.field.trashed:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The field with ID {group_by.field.id} is trashed."
                )
            try:
                grouped_aggregation_group_by_registry.get_by_type(
                    group_by.field.get_type()
                )
            except FieldTypeDoesNotExist:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The field with ID {group_by.field.id} cannot be used for group by."
                )
            group_by_values.append(group_by.field.db_column)

        if len(group_by_values) > 0:
            queryset = queryset.values(*group_by_values)

        combined_agg_dict = {}
        defined_agg_series = service.service_aggregation_series.all()
        if len(defined_agg_series) == 0:
            raise ServiceImproperlyConfiguredDispatchException(
                f"There are no aggregation series defined."
            )

        series_agg_used = set()
        for agg_series in defined_agg_series:
            if agg_series.field is None:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The aggregation series field has to be set."
                )
            if agg_series.field.trashed:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The field with ID {agg_series.field.id} is trashed."
                )
            model_field = model._meta.get_field(agg_series.field.db_column)
            try:
                agg_type = grouped_aggregation_registry.get(agg_series.aggregation_type)
            except AggregationTypeDoesNotExist as ex:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The the aggregation type {agg_series.aggregation_type} doesn't exist."
                ) from ex
            if not agg_type.field_is_compatible(agg_series.field):
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The field with ID {agg_series.field.id} is not compatible "
                    f"with the aggregation type {agg_series.aggregation_type}."
                )

            series_aggregation_reference = (
                f"field_{agg_series.field.id}_{agg_series.aggregation_type}"
            )
            if series_aggregation_reference in series_agg_used:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The series with field ID {agg_series.field.id} and "
                    f"aggregation type {agg_series.aggregation_type} can only be defined once."
                )
            else:
                if agg_series.field and agg_series.aggregation_type:
                    series_agg_used.add(series_aggregation_reference)

            combined_agg_dict |= agg_type._get_aggregation_dict(
                queryset, model_field, agg_series.field, include_agg_type=True
            )

        for key, value in combined_agg_dict.items():
            if isinstance(value, AnnotatedAggregation):
                queryset = queryset.annotate(**value.annotations)
                other_buckets_qs = other_buckets_qs.annotate(**value.annotations)
                combined_agg_dict[key] = value.aggregation

        allowed_sort_references = [
            f"field_{series.field_id}_{series.aggregation_type}"
            for series in service.service_aggregation_series.all()
            if series.aggregation_type is not None and series.field_id is not None
        ]

        if service.service_aggregation_group_bys.count() > 0:
            group_by = service.service_aggregation_group_bys.all()[0]
            allowed_sort_references += (
                [f"field_{group_by.field_id}"]
                if group_by.field_id is not None
                else [f"field_{model.get_primary_field().id}"]
            )

        sorts = []
        sort_annotations = {}
        for sort_by in service.service_aggregation_sorts.all():
            if sort_by.reference not in allowed_sort_references:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The sort reference '{sort_by.reference}' cannot be used for sorting."
                )

            if sort_by.sort_on == "SERIES":
                expression = F(f"{sort_by.reference}_raw")
                if sort_by.direction == "ASC":
                    expression = expression.asc(nulls_first=True)
                else:
                    expression = expression.desc(nulls_last=True)
                sorts.append(expression)
            else:
                field_obj = model.get_field_object(sort_by.reference)
                field_type = field_obj["type"]
                field_annotated_order_by = field_type.get_order(
                    field=field_obj["field"],
                    field_name=sort_by.reference,
                    order_direction=sort_by.direction,
                    # The application builder does not yet have compatibility with
                    # different sort types, so it uses the default one instead.
                    sort_type=DEFAULT_SORT_TYPE_KEY,
                )
                if field_annotated_order_by.annotation is not None:
                    sort_annotations = {
                        **sort_annotations,
                        **field_annotated_order_by.annotation,
                    }
                field_order_bys = field_annotated_order_by.order_bys
                for field_order_by in field_order_bys:
                    sorts.append(field_order_by)

        queryset = queryset.annotate(**sort_annotations)
        group_by_fields = [
            model.get_primary_field() if group_by.field is None else group_by.field
            for group_by in service.service_aggregation_group_bys.all()
        ]
        group_by_value_serializers_by_db_column = {
            field.db_column: field.get_type().get_query_value_serializer(field.specific)
            for field in group_by_fields
        }

        def process_individual_result(result: dict, index: int):
            result = {**result}
            for agg_series in defined_agg_series:
                key = f"{agg_series.field.db_column}_{agg_series.aggregation_type}"
                raw_value = result.pop(f"{key}_raw")
                agg_type = grouped_aggregation_registry.get(agg_series.aggregation_type)
                result[key] = agg_type._compute_final_aggregation(
                    raw_value, result.get("total", None)
                )
            if "total" in result:
                del result["total"]
            result[GROUPED_AGGREGATE_ROW_ID] = self._get_result_record_id(
                service, result, index, model
            )
            for (
                db_column,
                serialize_value,
            ) in group_by_value_serializers_by_db_column.items():
                if db_column not in result:
                    continue
                result[db_column] = serialize_value(result[db_column])
            return result

        if len(group_by_values) > 0:
            queryset = queryset.annotate(**combined_agg_dict)
            queryset = queryset.order_by(*sorts)
            queryset = queryset[
                : settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS + 1
            ]
            raw_results = list(queryset)

            results = [
                process_individual_result(result, index)
                for index, result in enumerate(raw_results)
            ]
            buckets_count = len(raw_results)
            if (
                buckets_count
                > settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS
            ):
                # The number of buckets don't fit in the limit
                # so we will aggregate all the other buckets into one
                bucket_db_column = group_by_values[0]
                raw_results = raw_results[
                    : settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS
                    - 1
                ]
                results = results[
                    : settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS
                    - 1
                ]
                buckets_taken = [result[bucket_db_column] for result in raw_results]
                other_buckets_qs = other_buckets_qs.exclude(
                    **{f"{bucket_db_column}__in": buckets_taken}
                )

                other_bucket_results = other_buckets_qs.aggregate(**combined_agg_dict)
                other_bucket_primary_field = (
                    {f"{model.get_primary_field().db_column}": "OTHER_VALUES"}
                    if "id" in group_by_values
                    else {}
                )
                other_bucket_results = process_individual_result(
                    {
                        bucket_db_column: "OTHER_VALUES",
                        **other_bucket_primary_field,
                        **other_bucket_results,
                    },
                    len(results),
                )
                results.append(other_bucket_results)
                first_sort_by = service.service_aggregation_sorts.first()
                if first_sort_by and first_sort_by.sort_on == "SERIES":
                    results = sorted(
                        results,
                        key=lambda x: x[first_sort_by.reference],
                        reverse=True if first_sort_by.direction == "DESC" else False,
                    )
        else:
            results = queryset.aggregate(**combined_agg_dict)
            results = process_individual_result(results, 0)
            results = [results]

        if dispatch_context.only_record_id is not None:
            current_record_id = str(dispatch_context.only_record_id)
            results = [
                result
                for result in results
                if result[GROUPED_AGGREGATE_ROW_ID] == current_record_id
            ]

        results = [
            self._convert_result_property_names_to_human_names(service, result)
            for result in results
        ]

        return {
            "data": {"results": results, "has_next_page": False},
            "baserow_table_model": model,
        }

    def dispatch_transform(
        self,
        data: any,
    ) -> DispatchResult:
        return DispatchResult(data=data["data"])

    def sanitize_result(self, service, result, allowed_field_names):
        """
        Filter against the human names returned by grouped aggregation dispatch.
        """

        allowed_field_names = self._convert_allowed_field_names(
            service, allowed_field_names
        )

        return ServiceType.sanitize_result(self, service, result, allowed_field_names)

    def extract_properties(
        self, service: Service, path: list[str], **kwargs
    ) -> list[str]:
        result_properties = self._get_result_properties(service) or {}

        if not path:
            return list(result_properties.keys())

        # DataSourceDataProviderType and CurrentRecordDataProviderType strip the row
        # selector from list paths before calling the service extractor.
        if len(path) >= 1 and path[0] in result_properties:
            return [path[0]]

        return []
