from typing import TYPE_CHECKING, Dict, Generator, List, Optional, Tuple, Type, Union

from django.db.models import OrderBy, Prefetch, QuerySet

from baserow.contrib.database.api.utils import extract_field_ids_from_list
from baserow.contrib.database.fields.field_filters import FilterBuilder
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.contrib.integrations.local_baserow.api.serializers import (
    LocalBaserowTableServiceFilterSerializerMixin,
    LocalBaserowTableServiceSortSerializerMixin,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
    LocalBaserowViewService,
)
from baserow.core.formula import BaserowFormulaObject, resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.formula.validator import ensure_integer, ensure_string
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceFilterPropertyDoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
    ServiceSortPropertyDoesNotExist,
)
from baserow.core.services.types import (
    FormulaToResolve,
    ServiceDict,
    ServiceFilterDictSubClass,
    ServiceSortDictSubClass,
    ServiceSubClass,
)
from baserow.core.services.utils import ServiceAdhocRefinements
from baserow.core.utils import atomic_if_not_already

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel, Table
    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowTableService,
    )


class LocalBaserowTableServiceFilterableMixin:
    """
    A mixin for LocalBaserow{Table,View}Service services so that when they dispatch,
    filters applied to their service's table, and possibly view, are applied to
    the queryset.
    """

    mixin_allowed_fields = ["filter_type"]
    mixin_serializer_field_names = ["filter_type"]
    mixin_serializer_field_overrides = {}
    mixin_serializer_mixins = [LocalBaserowTableServiceFilterSerializerMixin]

    class SerializedDict(ServiceDict):
        filter_type: str
        filters: List[Dict]

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                Prefetch(
                    "service_filters",
                    queryset=LocalBaserowTableServiceFilter.objects.select_related(
                        "field"
                    ).all(),
                ),
            )
        )

    def serialize_filters(self, service: ServiceSubClass):
        """
        Responsible for serializing the service `filters`.

        :param service: the service instance.
        :return: A list of serialized filter dictionaries.
        """

        return [
            {
                "field_id": f.field_id,
                "type": f.type,
                "value": f.value,
                "value_is_formula": f.value_is_formula,
            }
            for f in service.service_filters_with_untrashed_fields
        ]

    def serialize_property(
        self,
        service: ServiceSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `filters` properties.

        :param service: The LocalBaserowListRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "filters":
            return self.serialize_filters(service)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_filters(self, value, id_mapping):
        """
        Deserializes the filters by mapping the field_id to the new field_id if it
        exists in the id_mapping. If the value is a digit, try and map the value to
        the new field select option id.

        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for the filter.
        """

        result = []

        for f in value:
            formula = BaserowFormulaObject.to_formula(f["value"])
            field_id = id_mapping.get("database_fields", {}).get(
                f["field_id"], f["field_id"]
            )

            if (
                f["value_is_formula"]
                or not formula["formula"].isdigit()
                or "database_field_select_options" not in id_mapping
            ):
                val = formula
            else:
                val = BaserowFormulaObject.create(
                    formula=str(
                        id_mapping["database_field_select_options"].get(
                            int(formula["formula"]), formula["formula"]
                        )
                    ),
                    mode=formula["mode"],
                    version=formula["version"],
                )

            result.append({**f, "field_id": field_id, "value": val})

        return result

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> ServiceSubClass:
        """
        Responsible for creating the `filters`.

        :param serialized_values: The serialized values we'll use to import.
        :param id_mapping: The id_mapping dictionary.
        :return: A Service.
        """

        filters = serialized_values.pop("filters", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # Create filters
        LocalBaserowTableServiceFilter.objects.bulk_create(
            [
                LocalBaserowTableServiceFilter(
                    **service_filter,
                    order=index,
                    service=service,
                )
                for index, service_filter in enumerate(
                    self.deserialize_filters(filters, id_mapping)
                )
            ]
        )

        return service

    def get_used_field_names(
        self,
        service: "LocalBaserowTableService",
        dispatch_context: DispatchContext,
    ):
        """
        Add the fields that are related to the service filters.
        """

        used_fields_from_parent = super().get_used_field_names(
            service, dispatch_context
        )

        if isinstance(used_fields_from_parent, list):
            return used_fields_from_parent + [
                f"field_{service_filter.field_id}"
                for service_filter in service.service_filters_with_untrashed_fields
            ]

        return None

    def get_dispatch_filters(
        self,
        service: "ServiceSubClass",
        queryset: QuerySet,
        model: Type["GeneratedTableModel"],
        dispatch_context: DispatchContext,
    ) -> QuerySet:
        """
        Responsible for defining how the `LocalBaserow` services are filtered. To issue
        a `dispatch`, a `LocalBaserow` service must be pointing to a table.

        If we only have a `table` and no `view`, then we will query for, and apply,
        any `LocalBaserowTableServiceFilter` found for this service.

        If we also have a `view`, then we will query for, and apply, any `ViewFilter`
        found for this view.

        :param service: The `LocalBaserow` service we're dispatching.
        :param queryset: The queryset we want to filter upon.
        :param model: The `service.table`'s `GeneratedTableModel`.
        :return: A queryset with any applicable view/service filters applied to it.
        """

        if isinstance(service, LocalBaserowViewService) and service.view_id:
            view_filter_builder = ViewHandler().get_filter_builder(service.view, model)
            queryset = view_filter_builder.apply_to_queryset(queryset)

        # If there are filters pointing to trashed fields, throw an exception.
        # We won't allow the service to be dispatched as it could leak data.
        if len(service.service_filters_with_untrashed_fields) != len(
            service.service_filters.all()
        ):
            raise ServiceFilterPropertyDoesNotExist(
                "One or more filtered properties no longer exist.",
            )

        service_filter_builder = FilterBuilder(filter_type=service.filter_type)
        for service_filter in service.service_filters_with_untrashed_fields:
            field_object = model._field_objects[service_filter.field_id]
            field_name = field_object["name"]
            model_field = model._meta.get_field(field_name)
            view_filter_type = view_filter_type_registry.get(service_filter.type)

            # We need this test for compatibility purposes with old values
            if (
                service_filter.value_is_formula
                or service_filter.value["mode"] == BASEROW_FORMULA_MODE_RAW
            ):
                try:
                    resolved_value = ensure_string(
                        resolve_formula(
                            service_filter.value,
                            formula_runtime_function_registry,
                            dispatch_context,
                        )
                    )
                except Exception as exc:
                    raise ServiceImproperlyConfiguredDispatchException(
                        f"The {field_name} service filter formula can't be "
                        "resolved: {exc}"
                    ) from exc
            else:
                resolved_value = service_filter.value["formula"]

            service_filter_builder.filter(
                view_filter_type.get_filter(
                    field_name, resolved_value, model_field, field_object["field"]
                )
            )

        return service_filter_builder.apply_to_queryset(queryset)

    def formula_generator(
        self, service: "LocalBaserowTableServiceFilterableMixin"
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that iterates over formula fields for LocalBaserow Services.

        Some formula fields are in service filters.
        """

        yield from super().formula_generator(service)

        for service_filter in service.service_filters_with_untrashed_fields:
            is_formula = service_filter.value_is_formula
            formula = BaserowFormulaObject.to_formula(service_filter.value)

            if not is_formula:
                formula["mode"] = BASEROW_FORMULA_MODE_RAW

            # Service types like LocalBaserowGetRow do not have a value attribute.
            new_formula = yield formula
            if new_formula is not None:
                # Set the new formula for the Service Filter
                service_filter.value = new_formula
                yield service_filter

    def get_table_queryset(
        self,
        service: ServiceSubClass,
        table: "Table",
        dispatch_context: DispatchContext,
        model: Type["GeneratedTableModel"],
    ) -> QuerySet:
        """
        Responsible for applying the filters to the queryset. If the dispatch
        context contains any adhoc-filters, they are applied on top of existing
        service and view filters.

        :param service: the service instance.
        :param table: the table instance.
        :param dispatch_context: the dispatch context.
        :param model: the table's generated table model
        :return: the queryset with filters applied.
        """

        queryset = super().get_table_queryset(service, table, dispatch_context, model)
        queryset = self.get_dispatch_filters(service, queryset, model, dispatch_context)
        dispatch_filters = dispatch_context.filters()
        if dispatch_filters is not None and dispatch_context.is_publicly_filterable:
            deserialized_filters = AdHocFilters.deserialize_dispatch_filters(
                dispatch_filters
            )
            # Next we pluck out the field IDs which the filters point to.
            field_ids = list(set([f["field"] for f in deserialized_filters["filters"]]))
            # In bulk fetch the field records.
            fields = Field.objects.filter(pk__in=field_ids).only("id")
            # Extract the field db columns names.
            field_names = [field.db_column for field in fields]
            # Validate that the fields are filterable.
            dispatch_context.validate_filter_search_sort_fields(
                field_names, ServiceAdhocRefinements.FILTER
            )
            adhoc_filters = AdHocFilters.from_dict(deserialized_filters)
            queryset = adhoc_filters.apply_to_queryset(model, queryset)
        return queryset

    def update_service_filters(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_filters: Optional[List[ServiceFilterDictSubClass]] = None,
    ):
        with atomic_if_not_already():
            service.service_filters.all().delete()
            LocalBaserowTableServiceFilter.objects.bulk_create(
                [
                    LocalBaserowTableServiceFilter(
                        **service_filter, service=service, order=index
                    )
                    for index, service_filter in enumerate(service_filters)
                ]
            )

    def after_update(
        self,
        instance: ServiceSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ) -> None:
        """
        Responsible for updating service filters which have been
        PATCHED to the data source / service endpoint. At the moment we
        destroy all current filters, and create the ones present
        in `service_filters`.

        :param instance: The service we want to manage filters for.
        :param values: A dictionary which may contain filters.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        super().after_update(instance, values, changes)

        # Following a Table change, from one Table to another, we drop all filters.
        # This is due to the fact that they point at specific table fields.
        from_table, to_table = changes.get("table", (None, None))

        if from_table and to_table:
            instance.service_filters.all().delete()
        else:
            if "service_filters" in values:
                self.update_service_filters(instance, values["service_filters"])


class LocalBaserowTableServiceSortableMixin:
    """
    A mixin for LocalBaserowTableService services so that when they dispatch, sortings
    applied to their service's table or view are applied to the queryset.
    """

    mixin_serializer_field_names = []
    mixin_serializer_field_overrides = {}
    mixin_serializer_mixins = [LocalBaserowTableServiceSortSerializerMixin]

    class SerializedDict(ServiceDict):
        sortings: List[Dict]

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                Prefetch(
                    "service_sorts",
                    queryset=LocalBaserowTableServiceSort.objects.select_related(
                        "field"
                    ).all(),
                ),
            )
        )

    def serialize_sortings(self, service: ServiceSubClass):
        """
        Responsible for serializing the service `sortings`.

        :param service: the service instance.
        :return: A list of serialized sort dictionaries.
        """

        return [
            {
                "field_id": s.field_id,
                "order_by": s.order_by,
            }
            for s in service.service_sorts_with_untrashed_fields
        ]

    def serialize_property(
        self,
        service: ServiceSubClass,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `sortings` properties.

        :param service: The LocalBaserowListRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "sortings":
            return self.serialize_sortings(service)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def deserialize_sorts(self, value, id_mapping):
        """
        Deserializes the sorts by mapping the field_id to the new field_id if it
        exists in the id_mapping.

        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for the sort.
        """

        return [
            {
                **f,
                "field_id": (
                    id_mapping["database_fields"][f["field_id"]]
                    if "database_fields" in id_mapping
                    else f["field_id"]
                ),
            }
            for f in value
        ]

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> ServiceSubClass:
        """
        Responsible for creating the `sortings`.

        :param serialized_values: The serialized values we'll use to import.
        :param id_mapping: The id_mapping dictionary.
        :return: A Service.
        """

        sortings = serialized_values.pop("sortings", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # Create sortings
        LocalBaserowTableServiceSort.objects.bulk_create(
            [
                LocalBaserowTableServiceSort(
                    **service_sorting,
                    order=index,
                    service=service,
                )
                for index, service_sorting in enumerate(
                    self.deserialize_sorts(sortings, id_mapping)
                )
            ]
        )

        return service

    def get_used_field_names(
        self,
        service: "LocalBaserowTableService",
        dispatch_context: DispatchContext,
    ):
        """
        Add the fields related to the sort associated to the given service.
        """

        used_fields_from_parent = super().get_used_field_names(
            service, dispatch_context
        )

        if isinstance(used_fields_from_parent, list):
            return used_fields_from_parent + [
                f"field_{service_sort.field_id}"
                for service_sort in service.service_sorts_with_untrashed_fields
            ]

        return None

    def get_dispatch_sorts(
        self,
        service: "ServiceSubClass",
        queryset: QuerySet,
        model: Type["GeneratedTableModel"],
    ) -> Tuple[List[OrderBy], QuerySet]:
        """
        Responsible for defining how the `LocalBaserow` services are sorted. To issue
        a `dispatch`, a `LocalBaserow` service must be pointing to a table.

        If we find any `LocalBaserowTableServiceSort` applied to this service, we will
        *only* sort on their `OrderBy` expressions.

        If we find no `LocalBaserowTableServiceSort`, then we will attempt to find any
        `ViewSort` applied to the view, and use that for sorting the queryset.

        :param service: The `LocalBaserow` service we're dispatching.
        :param queryset: The Django queryset we want to apply our sort annotations to.
        :param model: The `service.view.table`'s `GeneratedTableModel`.
        :return: A list of `OrderBy` expressions.
        """

        # If there are sorts pointing to trashed fields, throw an exception.
        # We won't allow the service to be dispatched as it could leak data.
        if len(service.service_sorts_with_untrashed_fields) != len(
            service.service_sorts.all()
        ):
            raise ServiceSortPropertyDoesNotExist(
                "One or more sorted properties no longer exist.",
            )

        service_sorts = service.service_sorts_with_untrashed_fields
        sort_ordering = [service_sort.get_order_by() for service_sort in service_sorts]

        if not sort_ordering and service.view:
            sort_ordering, queryset = ViewHandler().get_view_order_bys(
                service.view, model, queryset
            )

        return sort_ordering, queryset

    def get_table_queryset(
        self,
        service: ServiceSubClass,
        table: "Table",
        dispatch_context: DispatchContext,
        model: Type["GeneratedTableModel"],
    ) -> QuerySet:
        """
        Responsible for applying the sortings to the queryset. If the dispatch
        context contains any adhoc-sortings, they replace any existing service
        and/or view sorts.

        :param service: the service instance.
        :param table: the table instance.
        :param dispatch_context: the dispatch context.
        :param model: the table's generated table model
        :return: the queryset with sortings applied.
        """

        queryset = super().get_table_queryset(service, table, dispatch_context, model)

        adhoc_sort = dispatch_context.sortings()
        if adhoc_sort and dispatch_context.is_publicly_sortable:
            field_names = [field.strip("-") for field in adhoc_sort.split(",")]
            dispatch_context.validate_filter_search_sort_fields(
                field_names, ServiceAdhocRefinements.SORT
            )
            queryset = queryset.order_by_fields_string(adhoc_sort, False)
        else:
            view_sorts, queryset = self.get_dispatch_sorts(service, queryset, model)
            if view_sorts:
                queryset = queryset.order_by(*view_sorts)
        return queryset

    def update_service_sortings(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_sorts: Optional[List[ServiceSortDictSubClass]] = None,
    ):
        with atomic_if_not_already():
            service.service_sorts.all().delete()
            LocalBaserowTableServiceSort.objects.bulk_create(
                [
                    LocalBaserowTableServiceSort(
                        **service_sort, service=service, order=index
                    )
                    for index, service_sort in enumerate(service_sorts)
                ]
            )

    def after_update(
        self,
        instance: ServiceSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ) -> None:
        """
        Responsible for updating service sorts which have been
        PATCHED to the data source / service endpoint. At the moment we
        destroy all current sorts, and create the ones present
        in `service_sorts`.

        :param instance: The service we want to manage sorts for.
        :param values: A dictionary which may contain sorts.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        super().after_update(instance, values, changes)

        # Following a Table change, from one Table to another, we drop all filters
        # and sorts. This is due to the fact that both point at specific table fields.
        from_table, to_table = changes.get("table", (None, None))

        if from_table and to_table:
            instance.service_sorts.all().delete()
        else:
            if "service_sorts" in values:
                self.update_service_sortings(instance, values["service_sorts"])


class LocalBaserowTableServiceSearchableMixin:
    """
    A mixin for `LocalBaserowTable` service types so that when they dispatch,
    search queries applied to their service's table are applied to the queryset.
    """

    mixin_simple_formula_fields = ["search_query"]
    mixin_allowed_fields = ["search_query"]
    mixin_serializer_field_names = ["search_query"]
    mixin_serializer_field_overrides = {
        "search_query": FormulaSerializerField(
            help_text="Any search queries to apply to the "
            "service when it is dispatched.",
        )
    }

    class SerializedDict(ServiceDict):
        search_query: str

    def get_used_field_names(
        self,
        service: "LocalBaserowTableService",
        dispatch_context: DispatchContext,
    ):
        """
        Add all tsv_vector columns used by the search.
        """

        used_fields_from_parent = super().get_used_field_names(
            service, dispatch_context
        )

        if isinstance(used_fields_from_parent, list) and service.search_query:
            fields = [fo["field"] for fo in self.get_table_field_objects(service) or []]
            search_fields = []
            if not SearchHandler.can_use_full_text_search(service.table):
                search_fields = [f.db_column for f in fields]
            return used_fields_from_parent + search_fields

        return used_fields_from_parent

    def get_dispatch_search(
        self, service: "ServiceSubClass", dispatch_context: DispatchContext
    ) -> str:
        """
        Returns this service's search query, which can be applied to the dispatch
        queryset.

        :param service: The `LocalBaserow` service we're dispatching.
        :return: string
        """

        try:
            return ensure_string(
                resolve_formula(
                    service.search_query,
                    formula_runtime_function_registry,
                    dispatch_context,
                ),
                allow_empty=True,
            )
        except Exception as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The `search_query` formula can't be resolved: {exc}"
            ) from exc

    def get_table_queryset(
        self,
        service: ServiceSubClass,
        table: "Table",
        dispatch_context: DispatchContext,
        model: Type["GeneratedTableModel"],
    ):
        """
        Responsible for applying the search query to the queryset. If the dispatch
        context contains an adhoc-search-query, it is applied ontop of the existing
        service search query.

        :param service: the service instance.
        :param table: the table instance.
        :param dispatch_context: the dispatch context.
        :param model: the table's generated table model
        :return: the queryset with the search query applied.
        """

        queryset = super().get_table_queryset(service, table, dispatch_context, model)
        search_mode = SearchHandler.get_default_search_mode_for_table(table)
        service_search_query = self.get_dispatch_search(service, dispatch_context)
        if service_search_query:
            queryset = queryset.search_all_fields(
                service_search_query, search_mode=search_mode
            )
        adhoc_search_query = dispatch_context.search_query()
        if adhoc_search_query is not None and dispatch_context.is_publicly_searchable:
            # This mixin's `get_queryset` method does not validate any adhoc
            # refinements, as the search query is not a field. We instead
            # restrict the fields that we search against to only those which
            # the page designer has marked as searchable.
            only_search_by_field_names = dispatch_context.searchable_fields()
            if not only_search_by_field_names:
                # We've been given an adhoc search to use, but none of the
                # properties have been flagged as searchable, so we can't
                # return anything.
                return queryset.none()
            only_search_by_field_ids = extract_field_ids_from_list(
                only_search_by_field_names
            )
            queryset = queryset.search_all_fields(
                adhoc_search_query,
                only_search_by_field_ids=only_search_by_field_ids,
                search_mode=search_mode,
            )
        return queryset


class LocalBaserowTableServiceSpecificRowMixin:
    mixin_simple_formula_fields = ["row_id"]
    mixin_allowed_fields = ["row_id"]
    mixin_serializer_field_names = ["row_id"]
    mixin_serializer_field_overrides = {
        "row_id": FormulaSerializerField(
            help_text="A formula for defining the intended row.",
        ),
    }

    class SerializedDict(ServiceDict):
        row_id: BaserowFormulaObject

    def formulas_to_resolve(self, service: ServiceSubClass) -> list[FormulaToResolve]:
        """
        Returns the formula to resolve for this service.
        """

        super_formulas = super().formulas_to_resolve(service)

        # Ignore empty formulas
        if not service.row_id["formula"]:
            return super_formulas

        return super_formulas + [
            FormulaToResolve("row_id", service.row_id, ensure_integer, '"row_id"')
        ]
