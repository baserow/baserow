"""
Helpers behind the grid view group-by data response.

Groups are paginated as a tree: a "parent path" maps a prefix of the group-by
fields to the values identifying one group (e.g. ``{color: "Red"}``). The
response builder parses the request and serves it in one of two modes:

- **Depth mode** (``depth`` param): the handler returns every group at a single
  depth as one global page, which is then regrouped into per-parent pages.
- **Parent mode** (``parents`` param): the explicitly requested
  parent pages are fetched, optionally expanding each parent's descendants.

Each function below notes which mode it serves; the rest are shared request,
response, and key-building helpers used by both.
"""

import json
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import QueryDict

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from baserow.config.settings.utils import str_to_bool, try_int
from baserow.contrib.database.api.views.utils import serialize_group_by_data_pages
from baserow.contrib.database.fields.exceptions import OrderByFieldNotFound
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.views.constants import GROUP_BY_DATA_DEFAULT_LIMIT
from baserow.contrib.database.views.exceptions import ViewGroupByFieldNotSupported
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY, ViewGroupBy
from baserow.core.utils import split_comma_separated_string

GROUP_BY_DATA_DESCENDANT_MAX_GROUPS = 2000
# Only a coarse backstop: a deep tree legitimately produces one parent page per internal
# node. The per-level batched descent runs one query per level regardless of page count,
# so the visible-row window and the group cap are what actually bound the work.
GROUP_BY_DATA_DESCENDANT_MAX_PAGES = GROUP_BY_DATA_DESCENDANT_MAX_GROUPS


def parse_adhoc_view_group_bys(
    raw_group_by: Optional[str],
    model: Type[Model],
    allowed_field_ids: Optional[Iterable[int]] = None,
) -> Optional[List[ViewGroupBy]]:
    """
    Parses the ad-hoc ``group_by`` query parameter into unsaved ``ViewGroupBy``
    instances usable by the group-by data handler.

    The parameter uses the rows-endpoint sort string format
    (e.g. ``-field_1[default],field_2``). Publicly shared views let visitors
    group by fields the view itself is not grouped by, so when the parameter is
    present the group tree must be built from it instead of the saved view
    group-bys.

    :param raw_group_by: The raw ``group_by`` query parameter value.
    :param model: The generated table model whose field objects validate the
        referenced fields.
    :param allowed_field_ids: When provided, fields outside this set are
        rejected (e.g. hidden fields of a public view).
    :raises OrderByFieldNotFound: When a referenced field does not exist on the
        model or is not allowed.
    :raises ViewGroupByFieldNotSupported: When a referenced field cannot be
        grouped by.
    :return: The unsaved group-bys, or ``None`` when the parameter is missing
        or empty.
    """

    if not raw_group_by:
        return None

    if allowed_field_ids is not None:
        allowed_field_ids = set(allowed_field_ids)

    field_objects = model._field_objects
    group_bys = []
    for raw_entry in split_comma_separated_string(raw_group_by):
        field_id = get_field_id_from_field_key(raw_entry, strict=False)
        if (
            field_id is None
            or field_id not in field_objects
            or (allowed_field_ids is not None and field_id not in allowed_field_ids)
        ):
            raise OrderByFieldNotFound(raw_entry)

        order = "DESC" if raw_entry.startswith("-") else "ASC"
        type_match = re.search(r"\[(.*?)\]", raw_entry)
        sort_type = type_match.group(1) if type_match else DEFAULT_SORT_TYPE_KEY

        field_object = field_objects[field_id]
        if not field_object["type"].check_can_group_by(
            field_object["field"], sort_type
        ):
            raise ViewGroupByFieldNotSupported(
                f"It is not possible to group by field type "
                f"{field_object['type'].type} using sort type {sort_type}."
            )

        group_bys.append(ViewGroupBy(field_id=field_id, order=order, type=sort_type))

    return group_bys


def parse_non_negative_int(raw: Any, default: int) -> int:
    """
    Parses a non-negative integer from an untrusted query parameter value.

    :param raw: The raw query parameter value to parse.
    :param default: The value returned when ``raw`` is missing, not an integer,
        or negative.
    :return: The parsed integer, or ``default`` when it cannot be parsed or is
        negative.
    """

    value = try_int(raw, default)
    return value if value >= 0 else default


def deserialize_group_by_path_object(
    raw: Any, group_by_fields: List[Field]
) -> Optional[Dict[str, Any]]:
    """
    **Parent mode.** Deserializes a single parent path object into internal field
    values.

    A parent path maps a prefix of the group-by fields (by ``db_column``) to the
    values identifying which parent group a page belongs to. Each value is run
    through the field's group-by serializer so it matches the internal value used
    by the view handler. Parsing stops at the first field missing from ``raw``,
    which allows partial paths that target a shallower depth.

    :param raw: The raw path object, expected to be a ``dict`` keyed by
        ``db_column``.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :return: The deserialized path, an empty dict when ``raw`` is ``None``, or
        ``None`` when ``raw`` is not a dict or a value fails to deserialize.
    """

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None

    serializer_fields = {
        field.db_column: field_type_registry.get_by_model(
            field.specific_class
        ).get_group_by_serializer_field(field)
        for field in group_by_fields
    }
    deserialized = {}
    for field in group_by_fields:
        db_column = field.db_column
        if db_column not in raw:
            break

        raw_value = raw[db_column]
        if raw_value is None:
            deserialized[db_column] = None
            continue

        serializer_field = serializer_fields.get(db_column)
        if serializer_field is None:
            deserialized[db_column] = raw_value
            continue

        try:
            deserialized[db_column] = serializer_field.to_internal_value(raw_value)
        except (ValidationError, DjangoValidationError, ValueError, TypeError):
            return None

    return deserialized


def deserialize_group_by_parent_requests(
    query_params: QueryDict,
    group_by_fields: List[Field],
    default_offset: int,
    default_limit: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    **Parent mode.** Parses the requested group-by parent pages from the query
    string.

    :param query_params: The request query parameters.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param default_offset: The offset used when a parent request does not specify
        one.
    :param default_limit: The limit used when a parent request does not specify one.
    :return: A list of parent page request dicts, or ``None`` if the input is
        invalid. When a parent request provides ``parent_row_offset``, it is
        included so the backend can skip recomputing the parent's absolute row
        offset.
    """

    raw_parents = query_params.get("parents")
    if not raw_parents:
        return [
            {
                "parent": {},
                "offset": default_offset,
                "limit": default_limit,
            }
        ]

    try:
        raw_parent_requests = json.loads(raw_parents)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(raw_parent_requests, list):
        return None

    parent_requests = []
    for raw_parent_request in raw_parent_requests:
        if not isinstance(raw_parent_request, dict):
            return None

        raw_parent_row_offset = None
        if (
            "parent" in raw_parent_request
            or "path" in raw_parent_request
            or "offset" in raw_parent_request
            or "limit" in raw_parent_request
        ):
            raw_parent = raw_parent_request.get(
                "parent", raw_parent_request.get("path", {})
            )
            offset = parse_non_negative_int(
                raw_parent_request.get("offset"), default_offset
            )
            limit = min(
                parse_non_negative_int(raw_parent_request.get("limit"), default_limit),
                settings.ROW_PAGE_SIZE_LIMIT,
            )
            raw_parent_row_offset = raw_parent_request.get("parent_row_offset")
        else:
            raw_parent = raw_parent_request
            offset = default_offset
            limit = default_limit

        parent = deserialize_group_by_path_object(raw_parent, group_by_fields)
        if parent is None:
            return None

        parent_request = {
            "parent": parent,
            "offset": offset,
            "limit": limit,
        }
        if raw_parent_row_offset is not None:
            parent_request["parent_row_offset"] = parse_non_negative_int(
                raw_parent_row_offset, 0
            )
        parent_requests.append(parent_request)

    return parent_requests


def empty_group_by_data_page(
    parent: Optional[Dict[str, Any]] = None,
    offset: int = 0,
    limit: int = GROUP_BY_DATA_DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """
    Builds an empty group-by data page in the response shape.

    Returned when there is nothing to group (e.g. invalid input, or a depth page
    with no groups) so the response keeps the same structure as a populated page.

    :param parent: The parent path the page belongs to, defaulting to the root.
    :param offset: The offset the empty page reports.
    :param limit: The limit the empty page reports.
    :return: A page dict with no groups and a ``group_count`` of zero.
    """

    return {
        "parent": parent or {},
        "groups": [],
        "offset": offset,
        "limit": limit,
        "group_count": 0,
    }


def get_group_by_data_parent_path(
    group: Dict[str, Any], group_by_fields: List[Field]
) -> Dict[str, Any]:
    """
    **Depth mode.** Resolves the parent path of a single group within a depth
    page.

    Used while splitting a global depth page back into per-parent pages. Prefers
    the precomputed ``_parent_path`` annotation when present, otherwise derives it
    from the group's own ``path`` by taking the field prefix above its depth.

    :param group: The group dict as returned by the view handler.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :return: The parent path, keyed by ``db_column``.
    """

    if "_parent_path" in group:
        return group["_parent_path"]

    return {
        field.db_column: group["path"][field.db_column]
        for field in group_by_fields[: group["depth"]]
    }


def hashable_group_by_data_value(value: Any) -> Any:
    """
    Converts a group-by value into a hashable form usable in a key.

    Group-by values can be nested dicts or lists (e.g. multiple-collaborator or
    multiple-select fields), which cannot be placed directly in a set or tuple
    key. This recursively turns dicts and lists into sorted tuples so equal values
    always produce the same hashable key.

    :param value: The group-by value to convert.
    :return: A hashable representation of ``value``.
    """

    if isinstance(value, dict):
        return tuple(
            (key, hashable_group_by_data_value(item))
            for key, item in sorted(value.items())
        )
    if isinstance(value, list):
        return tuple(hashable_group_by_data_value(item) for item in value)
    return value


def group_by_data_page_key(
    parent: Dict[str, Any], group_by_fields: List[Field]
) -> Tuple[Any, ...]:
    """
    Builds a hashable key identifying a parent page.

    Used to bucket sibling groups when splitting a depth-mode page, and as the
    base of the parent-mode request key.

    :param parent: The parent path, keyed by ``db_column``.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :return: A tuple of ``(db_column, hashable value)`` pairs in field order.
    """

    return tuple(
        (
            field.db_column,
            hashable_group_by_data_value(parent[field.db_column]),
        )
        for field in group_by_fields
        if field.db_column in parent
    )


def split_group_by_depth_page_by_parent(
    depth_page: Dict[str, Any], group_by_fields: List[Field]
) -> List[Dict[str, Any]]:
    """
    **Depth mode.** Splits one globally paginated depth page into normal parent
    pages.

    :param depth_page: The global depth page returned by the view handler.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :return: Parent pages compatible with the existing group-by data response shape.
    """

    pages_by_key = {}
    for group in depth_page.get("groups", []):
        parent = get_group_by_data_parent_path(group, group_by_fields)
        page_key = group_by_data_page_key(parent, group_by_fields)
        page = pages_by_key.get(page_key)
        if page is None:
            page = {
                "parent": parent,
                "groups": [],
                "offset": group["sibling_index"],
                "limit": 0,
                "group_count": group.get("_parent_group_count", 0),
            }
            pages_by_key[page_key] = page

        page["groups"].append(group)
        page["offset"] = min(page["offset"], group["sibling_index"])
        page["limit"] = len(page["groups"])
        page["group_count"] = group.get("_parent_group_count", page["group_count"])

    if not pages_by_key:
        return [
            empty_group_by_data_page(
                offset=depth_page.get("offset", 0),
                limit=depth_page.get("limit", GROUP_BY_DATA_DEFAULT_LIMIT),
            )
        ]

    return list(pages_by_key.values())


def group_by_data_page_request_key(
    parent: Dict[str, Any],
    group_by_fields: List[Field],
    offset: int,
    limit: int,
) -> Tuple[Any, ...]:
    """
    **Parent mode.** Builds a hashable key identifying a specific parent page
    request.

    Extends the parent page key with the requested ``offset`` and ``limit`` so the
    fetch loop can skip parent pages already loaded, including those queued while
    expanding descendants.

    :param parent: The parent path, keyed by ``db_column``.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param offset: The requested offset within the parent's groups.
    :param limit: The requested number of groups.
    :return: A tuple of the parent key together with ``offset`` and ``limit``.
    """

    return group_by_data_page_key(parent, group_by_fields), offset, limit


def get_group_by_data_pages(
    view_handler: ViewHandler,
    base_queryset: QuerySet,
    view_group_bys: List[ViewGroupBy],
    group_by_fields: List[Field],
    parent_requests: List[Dict[str, Any]],
    include_descendants: bool = False,
    descendant_limit: int = GROUP_BY_DATA_DEFAULT_LIMIT,
    row_budget: int = GROUP_BY_DATA_DESCENDANT_MAX_GROUPS,
    aggregations: Optional[List[Tuple[Field, str]]] = None,
    aggregations_only: bool = False,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    **Parent mode.** Returns bounded group-by pages for the requested parents.

    When ``include_descendants`` is set, each parent's subtree is walked
    depth-first (pre-order) down to its leaves, so one request returns the whole
    visible subtree. Descent is bounded by an absolute row window: it anchors at
    ``start``, the first returned group's absolute row offset, and expands only
    groups whose ``row_offset`` falls within ``[start, start + row_budget)`` (the
    visible-viewport size); groups starting past the window render a placeholder and
    lazy-load on scroll. The page and group caps remain as backstops for
    pathological wide/deep trees.

    :param view_handler: The view handler used to fetch each group page.
    :param base_queryset: The filtered/searched rows queryset to group.
    :param view_group_bys: The view group-by configuration rows.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param parent_requests: The requested parent page dicts.
    :param include_descendants: Whether to recursively enqueue first child pages.
    :param descendant_limit: The maximum number of groups to return per descendant
        page.
    :param row_budget: The size of the absolute row-offset window
        ``[start, start + row_budget)`` within which descendant groups are expanded.
    :return: A tuple containing the collected pages and whether the response was
        truncated by a cap.
    """

    # No descendants: fetch each requested page individually, which reports empty pages,
    # their total sibling count, and arbitrary offsets exactly.
    if not include_descendants:
        pages = []
        seen = set()
        group_count = 0
        truncated = False
        for request in parent_requests:
            if (
                len(pages) >= GROUP_BY_DATA_DESCENDANT_MAX_PAGES
                or group_count >= GROUP_BY_DATA_DESCENDANT_MAX_GROUPS
            ):
                truncated = True
                break
            parent = request["parent"]
            request_key = group_by_data_page_request_key(
                parent, group_by_fields, request["offset"], request["limit"]
            )
            if request_key in seen:
                continue
            seen.add(request_key)
            page = view_handler.get_group_by_data(
                base_queryset,
                view_group_bys,
                parent_path=parent,
                offset=request["offset"],
                limit=request["limit"],
                parent_row_offset=request.get("parent_row_offset"),
                aggregations=aggregations,
                aggregations_only=aggregations_only,
            )
            page["parent"] = parent
            group_count += len(page.get("groups", []))
            pages.append(page)
        return pages, truncated

    pages = []
    seen = set()
    group_count = 0
    truncated = False

    # Resolve each parent's absolute row offset, computing it when the client didn't
    # thread it in (so threading stays a pure speedup). The descent then expands only
    # groups whose rows start within ``[start, start + row_budget)``, not the whole
    # breadth of a wide tree.
    initial_offset_by_key = {}
    for request in parent_requests:
        parent = request["parent"]
        parent_row_offset = request.get("parent_row_offset")
        if parent_row_offset is None:
            parent_row_offset = view_handler.get_group_by_path_row_offset(
                base_queryset, view_group_bys, parent
            )
        initial_offset_by_key[group_by_data_page_key(parent, group_by_fields)] = (
            parent_row_offset
        )
    # Anchor the window where the fetched groups start, not the parent's first row: a
    # scrolled slice (offset > 0) begins deep in the parent, so anchoring on the parent
    # offset would window the tree's top and expand nothing visible.
    window_end = None

    # Group parents by depth (and page slice) so each level is one batched query over
    # all its parents rather than a query per parent.
    waves: Dict[int, Dict[Tuple[int, int], List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for request in parent_requests:
        depth = sum(
            1 for field in group_by_fields if field.db_column in request["parent"]
        )
        waves[depth][(request["offset"], request["limit"])].append(request)

    stop = False
    while waves and not stop:
        depth = min(waves)
        for (offset, limit), requests in waves.pop(depth).items():
            parents = []
            offset_by_key = {}
            for request in requests:
                request_key = group_by_data_page_request_key(
                    request["parent"], group_by_fields, offset, limit
                )
                if request_key in seen:
                    continue
                seen.add(request_key)
                parents.append(request["parent"])
                parent_key = group_by_data_page_key(request["parent"], group_by_fields)
                offset_by_key[parent_key] = initial_offset_by_key.get(
                    parent_key, request.get("parent_row_offset") or 0
                )
            if not parents:
                continue

            groups = view_handler.get_group_by_data_for_parents(
                base_queryset,
                view_group_bys,
                parents,
                depth,
                offset=offset,
                per_parent_limit=limit,
                aggregations=aggregations,
            )

            # Split the batched groups into one page per parent, making each group's
            # parent-relative ``row_offset`` absolute via its parent's offset.
            page_by_key: Dict[Any, Dict[str, Any]] = {}
            page_order = []
            for group in groups:
                parent_key = group_by_data_page_key(
                    group["_parent_path"], group_by_fields
                )
                page = page_by_key.get(parent_key)
                if page is None:
                    page = {
                        "parent": group["_parent_path"],
                        "groups": [],
                        "offset": offset,
                        "limit": limit,
                        "group_count": group["_parent_group_count"],
                    }
                    page_by_key[parent_key] = page
                    page_order.append(parent_key)
                group["row_offset"] += offset_by_key.get(parent_key, 0)
                page["groups"].append(group)

            # A requested parent that yields no groups (e.g. a view whose filters
            # match nothing) must still report its empty page with exact counts,
            # or the client cannot tell a loaded-empty tree from an unloaded one.
            for parent in parents:
                parent_key = group_by_data_page_key(parent, group_by_fields)
                if parent_key in page_by_key:
                    continue
                page = view_handler.get_group_by_data(
                    base_queryset,
                    view_group_bys,
                    parent_path=parent,
                    offset=offset,
                    limit=limit,
                )
                page["parent"] = parent
                page_by_key[parent_key] = page
                page_order.append(parent_key)

            if window_end is None and page_by_key:
                group_row_offsets = [
                    group["row_offset"]
                    for page in page_by_key.values()
                    for group in page["groups"]
                ]
                if group_row_offsets:
                    window_end = row_budget + min(group_row_offsets)

            for parent_key in page_order:
                if (
                    len(pages) >= GROUP_BY_DATA_DESCENDANT_MAX_PAGES
                    or group_count >= GROUP_BY_DATA_DESCENDANT_MAX_GROUPS
                ):
                    truncated = True
                    stop = True
                    break
                page = page_by_key[parent_key]
                group_count += len(page["groups"])
                pages.append(page)
                for group in page["groups"]:
                    if group["row_offset"] >= window_end:
                        # Starts past the visible window; render a placeholder and
                        # lazy-load on scroll.
                        truncated = True
                        continue
                    if group.get("children_count", 0) <= 0:
                        continue
                    waves[depth + 1][(0, descendant_limit)].append(
                        {
                            "parent": group["path"],
                            "parent_row_offset": group["row_offset"],
                        }
                    )
            if stop:
                break

    return pages, truncated


def get_grid_view_group_by_aggregations(view, view_type) -> List[Tuple[Field, str]]:
    """
    Resolves the per-group aggregations to compute for a grid view's group-by data.

    Reuses the column footer aggregation configuration
    (``GridViewFieldOptions.aggregation_raw_type``) so a single "Summarize" choice
    drives both the grid footer and the per-group header values.

    :param view: The grid view to resolve the configured aggregations for.
    :param view_type: The resolved view type of ``view``.
    :return: The configured ``(field, aggregation_raw_type)`` pairs, or an empty
        list when the view type does not support field aggregations.
    """

    if not getattr(view_type, "can_aggregate_field", False):
        return []
    visible_field_ids = {
        option.field_id for option in view_type.get_visible_field_options_in_order(view)
    }
    return [
        (field.specific, raw_type)
        for field, raw_type in view_type.get_aggregations(view)
        if field.id in visible_field_ids
    ]


def build_group_by_data_response(
    view_handler: ViewHandler,
    request: Request,
    queryset: QuerySet,
    view_group_bys: List[ViewGroupBy],
    group_by_fields: List[Field],
    aggregations: Optional[List[Tuple[Field, str]]] = None,
    totals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    **Entry point.** Builds the serialized group-by data response for a grid view.

    Parses the pagination/scroll parameters from the request, dispatches to either
    depth mode or parent mode, and serializes the resulting pages. The
    authenticated and public grid views share this logic and only differ in how
    they build their filtered ``queryset``.

    :param view_handler: The view handler used to fetch each group page.
    :param request: The request carrying the group-by query parameters.
    :param queryset: The filtered/searched rows queryset to group.
    :param view_group_bys: The view group-by configuration rows.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param totals: The optional table-level aggregations to bundle top-level (when
        ``include_totals`` was requested), so the client can update the footer from
        the same request.
    :return: The serialized group-by data response.
    """

    aggregations_only = str_to_bool(str(request.GET.get("aggregations_only")))
    offset = parse_non_negative_int(request.GET.get("offset"), 0)
    limit = min(
        parse_non_negative_int(request.GET.get("limit"), GROUP_BY_DATA_DEFAULT_LIMIT),
        settings.ROW_PAGE_SIZE_LIMIT,
    )
    include_descendants = str_to_bool(str(request.GET.get("include_descendants")))
    descendant_limit = min(
        parse_non_negative_int(request.GET.get("descendant_limit"), limit),
        settings.ROW_PAGE_SIZE_LIMIT,
    )
    raw_depth = request.GET.get("depth")
    depth = (
        parse_non_negative_int(raw_depth, 0)
        if raw_depth is not None and raw_depth.strip() != ""
        else None
    )
    if depth is not None:
        depth_page = view_handler.get_group_by_data_for_depth(
            queryset,
            view_group_bys,
            depth=depth,
            offset=offset,
            limit=limit,
            aggregations=aggregations,
        )
        pages = split_group_by_depth_page_by_parent(depth_page, group_by_fields)
        truncated = False
    else:
        parent_requests = deserialize_group_by_parent_requests(
            request.GET, group_by_fields, offset, limit
        )
        if parent_requests is None:
            pages = [empty_group_by_data_page(offset=offset, limit=limit)]
            truncated = False
        else:
            # The client sends the row window that fills its screen in one descent,
            # defaulting to the page limit. Clamp to the group cap: a wider window can't
            # surface more than the cap allows.
            descendant_row_budget = max(
                1,
                min(
                    parse_non_negative_int(
                        request.GET.get("descendant_row_budget"), limit
                    ),
                    GROUP_BY_DATA_DESCENDANT_MAX_GROUPS,
                ),
            )
            pages, truncated = get_group_by_data_pages(
                view_handler,
                queryset,
                view_group_bys,
                group_by_fields,
                parent_requests,
                include_descendants=include_descendants,
                descendant_limit=descendant_limit,
                row_budget=(
                    descendant_row_budget
                    if include_descendants
                    else GROUP_BY_DATA_DESCENDANT_MAX_GROUPS
                ),
                aggregations=aggregations,
                aggregations_only=aggregations_only,
            )

    response = serialize_group_by_data_pages(
        pages, group_by_fields, truncated=truncated
    )
    if totals is not None:
        response["aggregations"] = totals
    return response
