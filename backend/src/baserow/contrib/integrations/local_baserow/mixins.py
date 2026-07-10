from typing import TYPE_CHECKING, Dict, Generator, List, Optional, Tuple, Type, Union

from django.db.models import OrderBy, Prefetch, QuerySet

from baserow.contrib.database.api.utils import extract_field_ids_from_list
from baserow.contrib.database.fields.field_filters import AdvancedFilterBuilder
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.integrations.local_baserow.api.serializers import (
    LocalBaserowTableServiceFilterSerializerMixin,
    LocalBaserowTableServiceSortSerializerMixin,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowListRows,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceFilterGroup,
    LocalBaserowTableServiceSort,
    LocalBaserowViewService,
)
from baserow.contrib.integrations.local_baserow.service_filter_groups import (
    LocalBaserowServiceGroupedFiltersAdapter,
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
        filter_groups: List[Dict]

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
                Prefetch(
                    "service_filter_groups",
                    queryset=LocalBaserowTableServiceFilterGroup.objects.all(),
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
                "group": f.group_id,
            }
            for f in service.service_filters_with_untrashed_fields
        ]

    def serialize_filter_groups(self, service: ServiceSubClass):
        """
        Responsible for serializing the service `filter_groups`.

        :param service: the service instance.
        :return: A list of serialized filter group dictionaries.
        """

        return [
            {
                "id": g.id,
                "filter_type": g.filter_type,
                "parent_group": g.parent_group_id,
            }
            for g in service.service_filter_groups.all()
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
        Responsible for serializing the `filters` and `filter_groups` properties.

        :param service: The LocalBaserowListRows service.
        :param prop_name: The property name we're serializing.
        :return: Any
        """

        if prop_name == "filters":
            return self.serialize_filters(service)

        if prop_name == "filter_groups":
            return self.serialize_filter_groups(service)

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
        filter_groups = serialized_values.pop("filter_groups", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        # Create the filter groups first, so that filters can reference them. Groups
        # are serialized with parents before children (see the model's `Meta.ordering`),
        # so the parent group has always been created (and mapped) by the time a child
        # references it.
        group_id_mapping = id_mapping.setdefault(
            "integration_service_filter_groups", {}
        )
        for filter_group in filter_groups:
            parent_group_id = filter_group["parent_group"]
            new_group = LocalBaserowTableServiceFilterGroup.objects.create(
                service=service,
                filter_type=filter_group["filter_type"],
                parent_group_id=group_id_mapping.get(parent_group_id)
                if parent_group_id is not None
                else None,
            )
            group_id_mapping[filter_group["id"]] = new_group.id

        # Create filters, mapping each filter's group to the newly-created group.
        LocalBaserowTableServiceFilter.objects.bulk_create(
            [
                LocalBaserowTableServiceFilter(
                    **{k: v for k, v in service_filter.items() if k != "group"},
                    group_id=group_id_mapping.get(service_filter.get("group"))
                    if service_filter.get("group") is not None
                    else None,
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

        # Build the service filters, nesting them into their filter groups (if any)
        # using the same machinery the database views use. Filters without a group
        # are combined under the service's top-level `filter_type`, preserving the
        # behaviour of services which don't use groups.
        adapter = LocalBaserowServiceGroupedFiltersAdapter(
            service, model, dispatch_context
        )
        service_filter_builder = AdvancedFilterBuilder(
            adapter
        ).construct_filter_builder()
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

    def sync_service_filter_groups(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_filter_groups: List[Dict],
    ) -> Dict[str, LocalBaserowTableServiceFilterGroup]:
        """
        Reconciles the service's filter groups against the given payload **in place**,
        preserving the primary keys of groups that already exist. Groups present in the
        payload are updated (or created when new), and groups no longer present are
        deleted.

        Preserving group primary keys is essential: filters reference their group by id,
        and because the data source is saved as a whole payload with only the changed
        keys sent, a partial update (e.g. only the filters, or only the groups) must not
        invalidate the links between the filters and groups that were not resent.

        Every incoming group id is treated as an opaque correlation key: it is either the
        id of an existing group (returned on read) or a client-generated id for a new
        group. Both are used only to link filters and nested groups together.

        :param service: The service the groups belong to.
        :param service_filter_groups: The list of validated filter group dictionaries.
        :return: A mapping of client group id to the persisted group instance.
        """

        existing_by_id = {
            str(group.id): group for group in service.service_filter_groups.all()
        }
        incoming_ids = {str(group["id"]) for group in service_filter_groups}

        # Delete groups which are no longer present in the payload. This cascades to
        # their filters, which is correct: removing a group removes its filters.
        for group_id, group in list(existing_by_id.items()):
            if group_id not in incoming_ids:
                group.delete()
                del existing_by_id[group_id]

        client_id_to_group: Dict[str, LocalBaserowTableServiceFilterGroup] = {}
        pending = list(service_filter_groups)

        def upsert(group, parent):
            group_id = str(group["id"])
            existing = existing_by_id.get(group_id)
            if existing is not None:
                existing.filter_type = group["filter_type"]
                existing.parent_group = parent
                existing.save()
                return existing
            return LocalBaserowTableServiceFilterGroup.objects.create(
                service=service,
                filter_type=group["filter_type"],
                parent_group=parent,
            )

        # Resolve parent references iteratively so that a parent group is always
        # persisted before its children, regardless of the order in the payload.
        while pending:
            still_pending = []
            for group in pending:
                parent_client_id = group.get("parent_group_id")
                parent_resolved = (
                    parent_client_id is None
                    or str(parent_client_id) in client_id_to_group
                )
                if not parent_resolved:
                    still_pending.append(group)
                    continue
                parent = (
                    client_id_to_group[str(parent_client_id)]
                    if parent_client_id is not None
                    else None
                )
                client_id_to_group[str(group["id"])] = upsert(group, parent)

            if len(still_pending) == len(pending):
                # No progress: the remaining groups reference missing parents. Persist
                # them as top-level groups so we never loop forever or lose data.
                for group in still_pending:
                    client_id_to_group[str(group["id"])] = upsert(group, None)
                break

            pending = still_pending

        return client_id_to_group

    def update_service_filters(
        self,
        service: Union[LocalBaserowGetRow, LocalBaserowListRows],
        service_filters: Optional[List[ServiceFilterDictSubClass]] = None,
        service_filter_groups: Optional[List[Dict]] = None,
    ):
        """
        Persists the given filters and/or filter groups for the service.

        Because the data source is saved as a whole payload but only the changed keys
        are sent, `service_filters` and/or `service_filter_groups` may be `None`,
        meaning "this part was not part of this update, leave it as-is". An empty list
        means "clear this part". This decoupling is what keeps a filter-only edit from
        wiping the groups (and vice versa).
        """

        with atomic_if_not_already():
            # Reconcile groups first (preserving their ids) so that filters can be
            # linked to them. When the groups are not part of this update, index the
            # existing groups by id so filters can still reference them.
            if service_filter_groups is not None:
                client_id_to_group = self.sync_service_filter_groups(
                    service, service_filter_groups
                )
            else:
                client_id_to_group = {
                    str(group.id): group
                    for group in service.service_filter_groups.all()
                }

            if service_filters is None:
                return

            service.service_filters.all().delete()

            def build_filter(index, service_filter):
                service_filter = {**service_filter}
                group_client_id = service_filter.pop("group_id", None)
                group = (
                    client_id_to_group.get(str(group_client_id))
                    if group_client_id is not None
                    else None
                )
                return LocalBaserowTableServiceFilter(
                    **service_filter, service=service, order=index, group=group
                )

            LocalBaserowTableServiceFilter.objects.bulk_create(
                [
                    build_filter(index, service_filter)
                    for index, service_filter in enumerate(service_filters)
                ]
            )

    def _invalidate_refinement_prefetch_cache(self, service):
        """
        The service may have been fetched with its filters/groups prefetched (see
        `enhance_queryset`). After mutating them, drop the stale prefetch cache so that
        a response serialized from the same instance reflects the changes.
        """

        prefetch_cache = getattr(service, "_prefetched_objects_cache", None)
        if prefetch_cache is not None:
            prefetch_cache.pop("service_filters", None)
            prefetch_cache.pop("service_filter_groups", None)

    def after_update(
        self,
        instance: ServiceSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ) -> None:
        """
        Responsible for updating the service filters and filter groups which have been
        PATCHED to the data source / service endpoint. Because only the changed keys are
        sent, filters and filter groups are updated independently: a part that is absent
        from the payload is left untouched (see `update_service_filters`).

        :param instance: The service we want to manage filters for.
        :param values: A dictionary which may contain `service_filters` and/or
            `service_filter_groups`.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        super().after_update(instance, values, changes)

        # Following a Table change, from one Table to another, we drop all filters and
        # filter groups. This is due to the fact that they point at specific table
        # fields.
        from_table, to_table = changes.get("table", (None, None))

        if from_table and to_table:
            instance.service_filters.all().delete()
            instance.service_filter_groups.all().delete()
            self._invalidate_refinement_prefetch_cache(instance)
        else:
            if "service_filters" in values or "service_filter_groups" in values:
                # Pass `None` (not `[]`) for a part that wasn't sent, so it is left
                # untouched rather than cleared. This is what keeps a filter-only edit
                # from wiping the groups, and a group-only edit from wiping the filters.
                self.update_service_filters(
                    instance,
                    values.get("service_filters"),
                    values.get("service_filter_groups"),
                )
                self._invalidate_refinement_prefetch_cache(instance)


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
