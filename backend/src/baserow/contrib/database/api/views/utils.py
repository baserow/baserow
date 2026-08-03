import math
from decimal import Decimal
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Set, Type

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models.query import QuerySet

from rest_framework.request import Request
from rest_framework.response import Response

from baserow.api.pagination import (
    LimitOffsetPagination,
    LimitOffsetPaginationWithoutCount,
    Pageable,
    PageNumberPagination,
    PageNumberPaginationWithoutCount,
)
from baserow.contrib.database.api.constants import (
    EXCLUDE_COUNT_API_PARAM,
    LIMIT_LINKED_ITEMS_API_PARAM,
)
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.api.views.serializers import serialize_group_by_metadata
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
    view_type_registry,
)


def get_public_view_authorization_token(request: Request) -> Optional[str]:
    """
    Returns the permission token to access a public view, if any.

    :param request: The request.
    :return: The public view permission token.
    """

    auth_header = request.headers.get(settings.PUBLIC_VIEW_AUTHORIZATION_HEADER, None)
    try:
        _, token = auth_header.split(" ", 1)
    except (AttributeError, ValueError):
        return None
    return token


def get_hidden_field_ids_for_view_user(
    user: AbstractUser, view: View
) -> Optional[Set[int]]:
    """
    Returns the set of field IDs that should be hidden from `user` in this view,
    or `None` if no restriction applies (all fields visible).
    """

    if hasattr(view, "_hidden_field_ids"):
        return view._hidden_field_ids
    ownership_type = view_ownership_type_registry.get(view.ownership_type)
    return ownership_type.get_hidden_field_ids_for_user(user, view)


def get_view_filtered_queryset(
    user: AbstractUser,
    view: Type[View],
    filters: Optional[AdHocFilters] = None,
    order_by: Optional[str] = None,
    query_params: Optional[Dict[str, Any]] = None,
    model: Optional[GeneratedTableModel] = None,
    hidden_field_ids: Optional[Set[int]] = None,
) -> QuerySet:
    """
    Returns a queryset that is filtered based on the provided view, adhoc filters, and
    query parameters (i.e. search value).

    :param user: The user on whose behalf the filtered queryset is requested. This is
        needed for permission checks.
    :param view: The view to filter the queryset by.
    :param filters: The adhoc filters to apply to the queryset.
    :param order_by: The order by string to apply to the queryset.
    :param query_params: The query parameters to apply to the queryset.
    :param model: The model to filter the queryset by.
    :param hidden_field_ids: Optional set of field IDs hidden from the user. When
        provided, search will be restricted to visible fields only.
    :return: The filtered queryset.
    """

    if model is None:
        model = view.table.get_model()

    if query_params is None:
        query_params = {}

    has_adhoc_filters = filters is not None and filters.has_any_filters
    has_adhoc_sorts = order_by is not None
    search_value = query_params.get("search")
    search_mode = query_params.get("search_mode")

    only_search_by_field_ids = None
    if hidden_field_ids:
        only_search_by_field_ids = [
            field_id
            for field_id in model._field_objects.keys()
            if field_id not in hidden_field_ids
        ]

    queryset = ViewHandler().get_queryset(
        user,
        view,
        apply_sorts=not has_adhoc_sorts,
        apply_filters=not has_adhoc_filters,
        search=search_value,
        search_mode=search_mode,
        model=model,
        only_search_by_field_ids=only_search_by_field_ids,
    )

    if has_adhoc_sorts:
        queryset = queryset.order_by_fields_string(order_by, False)

    if has_adhoc_filters:
        queryset = filters.apply_to_queryset(model, queryset)
    return queryset


class PublicViewFilteredQuerySet(NamedTuple):
    queryset: QuerySet
    field_ids: Iterable[int]
    publicly_visible_field_options: Dict[str, Any]


def get_public_view_filtered_queryset(
    view: Type[View], request: Request, query_params: Dict[str, Any]
) -> PublicViewFilteredQuerySet:
    """
    Returns a queryset that is filtered based on the provided publicly shared view and
    request.

    :param view: The publicly shared view to filter the queryset by.
    :param request: The request to filter the queryset by.
    :param query_params: The already validated request query parameters to filter the
        queryset by.
    :return: The filtered queryset.
    """

    search = query_params.get("search")
    search_mode = query_params.get("search_mode")
    order_by = request.GET.get("order_by")
    group_by = request.GET.get("group_by")
    include_fields = request.GET.get("include_fields")
    exclude_fields = request.GET.get("exclude_fields")
    adhoc_filters = AdHocFilters.from_request(request)
    view_type = view_type_registry.get_by_model(view)
    model = view.table.get_model()

    (
        queryset,
        field_ids,
        publicly_visible_field_options,
    ) = ViewHandler().get_public_rows_queryset_and_field_ids(
        view,
        search=search,
        search_mode=search_mode,
        order_by=order_by,
        group_by=group_by,
        include_fields=include_fields,
        exclude_fields=exclude_fields,
        adhoc_filters=adhoc_filters,
        table_model=model,
        view_type=view_type,
    )
    return PublicViewFilteredQuerySet(
        queryset=queryset,
        field_ids=field_ids,
        publicly_visible_field_options=publicly_visible_field_options,
    )


class PaginatedData(NamedTuple):
    response: Response
    page: QuerySet
    paginator: Pageable


def _get_paginator(request: Request) -> Pageable:
    """
    Returns the paginator to use based on the request query parameters.

    :param request: The request containing the pagination query parameters.
    :return: The paginator to use.
    """

    if EXCLUDE_COUNT_API_PARAM.name in request.GET:
        if LimitOffsetPagination.limit_query_param in request.GET:
            paginator = LimitOffsetPaginationWithoutCount()
        else:
            paginator = PageNumberPaginationWithoutCount()
    else:
        if LimitOffsetPagination.limit_query_param in request.GET:
            paginator = LimitOffsetPagination()
        else:
            paginator = PageNumberPagination()
    return paginator


def parse_limit_linked_items_params(request) -> Optional[int]:
    """
    Parses the limit linked items parameters from the request.

    :param request: The request containing the limit linked items parameters.
    :return: The parsed limit linked items parameters as an integer, or None if not set
        or invalid.
    """

    value = 0

    limit_linked_items = request.GET.get(LIMIT_LINKED_ITEMS_API_PARAM.name, None)
    if limit_linked_items is not None:
        try:
            value = int(limit_linked_items)
        except ValueError:
            pass

    return value if value > 0 else None


def paginate_and_serialize_queryset(
    queryset: QuerySet[GeneratedTableModel],
    request: Request,
    field_ids: Optional[Iterable[int]],
    exclude_field_ids: Optional[Iterable[int]] = None,
) -> PaginatedData:
    """
    Paginate and serialize the data for the provided queryset and view.

    :param queryset: The queryset to paginate and serialize.
    :param request: The request containing the pagination query parameters.
    :param field_ids: The (optional) field IDs to restrict the serialized data to.
    :param exclude_field_ids: Field IDs hidden by restricted view ownership. None
        means no restriction applies.
    :return: The paginated data containing the paginator, the page of results, and
        response containing the serialized data.
    """

    paginator = _get_paginator(request)
    page = paginator.paginate_queryset(queryset, request)

    limit_linked_items = parse_limit_linked_items_params(request)
    extra_kwargs = {"limit_linked_items": limit_linked_items}

    serializer_class = get_row_serializer_class(
        queryset.model,
        RowSerializer,
        is_response=True,
        field_ids=field_ids,
        exclude_field_ids=exclude_field_ids,
        extra_kwargs=extra_kwargs,
    )
    serializer = serializer_class(page, many=True)

    response = paginator.get_paginated_response(serializer.data)
    return PaginatedData(response, page, paginator)


def serialize_view_field_options(
    view: Type[View],
    model: GeneratedTableModel,
    create_if_missing: bool = True,
    context: Optional[Dict[str, Any]] = None,
    exclude_field_ids: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """
    Serializes the view field options for the provided view and the given model.

    :param view: The view to serialize the field options for.
    :param model: The model to serialize the field options for.
    :param create_if_missing: Whether to create the field options if they are missing.
    :param context: The context to serialize the field options with.
    :param exclude_field_ids: Field IDs hidden by restricted view ownership. None
        means no restriction applies.
    :return: The serialized view field options.
    """

    if context is None:
        fields = [o["field"] for o in model._field_objects.values()]
        if exclude_field_ids is not None:
            fields = [f for f in fields if f.id not in exclude_field_ids]
        context = {"fields": fields}

    view_type = view_type_registry.get_by_model(view)
    serializer_class = view_type.get_field_options_serializer_class(
        create_if_missing=create_if_missing
    )
    return serializer_class(view, context=context).data


def serialize_rows_metadata(
    user: AbstractUser, view: Type[View], rows: QuerySet[GeneratedTableModel]
) -> Dict[str, Any]:
    """
    Serializes the metadata for the provided rows.

    :param user: The user to serialize the metadata for.
    :param view: The view to serialize the metadata for.
    :param rows: The rows to serialize the metadata for.
    :return: The serialized metadata for the provided rows.
    """

    return row_metadata_registry.generate_and_merge_metadata_for_rows(
        user, view.table, (row.id for row in rows)
    )


def serialize_single_row_metadata(
    user: AbstractUser, row: GeneratedTableModel
) -> Dict[str, Any]:
    """
    Serializes the metadata for the provided row.

    :param user: The user to serialize the metadata for.
    :param row: The row to serialize the metadata for.
    :return: The serialized metadata for the provided rows.
    """

    return row_metadata_registry.generate_and_merge_metadata_for_row(
        user, row.baserow_table, row.id
    )


def serialize_group_by_fields_metadata(
    queryset: QuerySet[GeneratedTableModel],
    group_by_fields: List[Field],
    page: QuerySet[GeneratedTableModel],
):
    group_by_metadata = ViewHandler().get_group_by_metadata_in_rows(
        group_by_fields, page, queryset
    )
    serialized_group_by_metadata = serialize_group_by_metadata(group_by_metadata)
    return serialized_group_by_metadata


def _resolve_page_display_lists(
    containers: List[Dict[str, Any]],
    field_by_db_column: Dict[str, Field],
    type_by_db_column: Dict[str, Any],
) -> Dict[str, List[Any]]:
    """
    Resolves reference display values for one page's containers (``[parent]`` + group
    paths), keyed by ``db_column`` and parallel to ``containers``.
    """

    display_lists: Dict[str, List[Any]] = {}
    for db_column, field_type in type_by_db_column.items():
        present_indexes = [
            index
            for index, container in enumerate(containers)
            if container.get(db_column) is not None
        ]
        if not present_indexes:
            continue
        present_values = [containers[index][db_column] for index in present_indexes]
        displays = field_type.get_group_by_display_values(
            field_by_db_column[db_column], db_column, present_values
        )
        if displays is None:
            continue
        full: List[Any] = [None] * len(containers)
        for index, display in zip(present_indexes, displays):
            full[index] = display
        display_lists[db_column] = full
    return display_lists


def _resolve_group_by_display_lists(
    pages: List[Dict[str, Any]],
    field_by_db_column: Dict[str, Field],
    type_by_db_column: Dict[str, Any],
) -> List[Dict[str, List[Any]]]:
    """
    Resolves reference display values for every page in one query per field.

    ``get_group_by_display_values`` resolves a linked/reference field via its own
    table model and a single ``id__in`` query, so calling it once with the values
    from every page avoids the per-page N+1 the descended subtree would otherwise
    trigger. Returns a list parallel to ``pages``; each entry maps ``db_column`` to a
    list of displays parallel to that page's containers (``[parent]`` + group paths).
    """

    page_containers = [
        [page.get("parent", {})] + [group["path"] for group in page.get("groups", [])]
        for page in pages
    ]
    display_lists_per_page: List[Dict[str, List[Any]]] = [{} for _ in pages]
    for db_column, field_type in type_by_db_column.items():
        positions: List[tuple] = []
        values: List[Any] = []
        for page_index, containers in enumerate(page_containers):
            for container_index, container in enumerate(containers):
                if container.get(db_column) is not None:
                    positions.append((page_index, container_index))
                    values.append(container[db_column])
        if not values:
            continue
        displays = field_type.get_group_by_display_values(
            field_by_db_column[db_column], db_column, values
        )
        if displays is None:
            continue
        for (page_index, container_index), display in zip(positions, displays):
            full = display_lists_per_page[page_index].get(db_column)
            if full is None:
                full = [None] * len(page_containers[page_index])
                display_lists_per_page[page_index][db_column] = full
            full[container_index] = display
    return display_lists_per_page


def json_safe_aggregation_value(value: Any) -> Any:
    # Decimal("NaN") isn't JSON-serializable (it renders as the invalid JSON `NaN`
    # token), so it's substituted with its string form. Ideally each field type would
    # own how its aggregated value is represented; this single helper keeps that
    # concern in one place until that field-type-level refactor is worth doing.
    if isinstance(value, (float, Decimal)) and math.isnan(value):
        return "NaN"
    if isinstance(value, (float, Decimal)) and math.isinf(value):
        return "-Infinity" if value < 0 else "Infinity"
    return value


def serialize_group_by_data(
    page: Dict[str, Any],
    group_by_fields: List[Field],
    display_lists: Optional[Dict[str, List[Any]]] = None,
) -> Dict[str, Any]:
    """
    Serializes one group-by data page into its API representation.

    The inverse of the parent-path deserialization done when reading the request:
    each value in a group's ``path`` (and in the page's ``parent`` path) is
    converted to its API representation via the field's group-by serializer, while
    the pagination metadata is passed through. ``children_count`` is only included
    when the handler provided it.

    :param page: The group-by data page, with ``parent``, ``groups``, ``offset``,
        ``limit`` and ``group_count`` keys.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param display_lists: Optional pre-resolved header display values keyed by
        ``db_column``, parallel to the page's containers (its ``parent`` path
        followed by each group ``path``). Lets the caller resolve reference display
        values across all pages in one query per field; when ``None`` they are
        resolved per page here.
    :return: The serialized page in the API response shape.
    """

    field_by_db_column = {field.db_column: field for field in group_by_fields}
    type_by_db_column = {
        field.db_column: field_type_registry.get_by_model(field.specific_class)
        for field in group_by_fields
    }
    serializer_by_db_column = {
        db_column: field_type.get_group_by_serializer_field(
            field_by_db_column[db_column]
        )
        for db_column, field_type in type_by_db_column.items()
    }

    def serialize_path(path: Dict[str, Any]) -> Dict[str, Any]:
        serialized_path = {}
        for db_column, value in path.items():
            serializer_field = serializer_by_db_column.get(db_column)
            if value is None or serializer_field is None:
                serialized_path[db_column] = value
            else:
                serialized_path[db_column] = serializer_field.to_representation(value)
        return serialized_path

    # Display values for group-by headers, parallel to `containers`. The caller may
    # resolve them across all pages in one query per field; otherwise fall back to a
    # per-page resolution here.
    containers = [page.get("parent", {})] + [
        group["path"] for group in page.get("groups", [])
    ]
    if display_lists is None:
        display_lists = _resolve_page_display_lists(
            containers, field_by_db_column, type_by_db_column
        )

    def serialize_display(container_index: int) -> Dict[str, Any]:
        display = {}
        for db_column, full in display_lists.items():
            if full[container_index] is not None:
                display[db_column] = full[container_index]
        return display

    groups = []
    for group_index, group in enumerate(page.get("groups", [])):
        out_group = {
            "path": serialize_path(group["path"]),
            "depth": group["depth"],
        }
        # Layout keys are omitted in the lean "aggregations only" mode, so only
        # copy the ones the handler provided.
        for layout_key in (
            "row_count",
            "sibling_index",
            "row_offset",
            "children_count",
        ):
            if layout_key in group:
                out_group[layout_key] = group[layout_key]
        # `containers[0]` is the parent, so the groups start at index 1.
        display = serialize_display(group_index + 1)
        if display:
            out_group["display"] = display
        if "aggregations" in group:
            out_group["aggregations"] = {
                db_column: json_safe_aggregation_value(value)
                for db_column, value in group["aggregations"].items()
            }
        groups.append(out_group)

    return {
        "parent": serialize_path(page.get("parent", {})),
        "groups": groups,
        "offset": page.get("offset", 0),
        "limit": page.get("limit", 0),
        "group_count": page.get("group_count", 0),
    }


def serialize_group_by_data_pages(
    pages: List[Dict[str, Any]],
    group_by_fields: List[Field],
    truncated: bool = False,
) -> Dict[str, Any]:
    """
    Serializes the group-by data pages into the final response body.

    :param pages: The group-by data pages to serialize.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param truncated: Whether the pages were capped by a safety limit. When
        ``True`` a ``truncated`` flag is added to the response so the client knows
        more data was available.
    :return: The response body with a ``pages`` list and an optional ``truncated``
        flag.
    """

    field_by_db_column = {field.db_column: field for field in group_by_fields}
    type_by_db_column = {
        field.db_column: field_type_registry.get_by_model(field.specific_class)
        for field in group_by_fields
    }
    # Resolve reference display values for every page in one query per field instead of
    # once per page, which would be an N+1 across the descended subtree's pages.
    display_lists_per_page = _resolve_group_by_display_lists(
        pages, field_by_db_column, type_by_db_column
    )

    response = {
        "pages": [
            serialize_group_by_data(
                page, group_by_fields, display_lists=display_lists_per_page[index]
            )
            for index, page in enumerate(pages)
        ]
    }
    if truncated:
        response["truncated"] = True
    return response
