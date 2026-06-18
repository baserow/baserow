"""
Helpers behind the grid view group-by data response.

Groups are paginated as a tree: a "parent path" maps a prefix of the group-by
fields to the values identifying one group (e.g. ``{color: "Red"}``). The
response builder parses the request and serves it in one of two modes:

- **Depth mode** (``depth`` param): the handler returns every group at a single
  depth as one global page, which is then regrouped into per-parent pages.
- **Parent mode** (``parent``/``parents`` params): the explicitly requested
  parent pages are fetched, optionally expanding each parent's descendants.

Each function below notes which mode it serves; the rest are shared request,
response, and key-building helpers used by both.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.query import QuerySet
from django.http import QueryDict

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from baserow.config.settings.utils import str_to_bool, try_int
from baserow.contrib.database.api.views.utils import serialize_group_by_data_pages
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.constants import GROUP_BY_DATA_DEFAULT_LIMIT
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewGroupBy

GROUP_BY_DATA_DESCENDANT_MAX_PAGES = 50
GROUP_BY_DATA_DESCENDANT_MAX_GROUPS = 2000


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


def deserialize_group_by_path(
    raw_path: Optional[str], group_by_fields: List[Field]
) -> Optional[Dict[str, Any]]:
    """
    **Parent mode.** Deserializes a JSON-encoded parent path from a single query
    parameter.

    Decodes the JSON string carried by the ``parent`` query parameter, then
    deserializes it into internal field values like a parsed path object.

    :param raw_path: The JSON-encoded path string, or ``None``/empty when no
        parent is requested.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :return: The deserialized path, an empty dict when ``raw_path`` is empty, or
        ``None`` when the JSON is invalid or a value fails to deserialize.
    """

    if not raw_path:
        return {}

    try:
        raw = json.loads(raw_path)
    except (TypeError, json.JSONDecodeError):
        return None

    return deserialize_group_by_path_object(raw, group_by_fields)


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
        parent = deserialize_group_by_path(query_params.get("parent"), group_by_fields)
        if parent is None:
            return None
        return [
            {
                "parent": parent,
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
            (key, hashable_group_by_data_value(value))
            for key, value in sorted(value.items())
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
    total_group_limit: int = GROUP_BY_DATA_DESCENDANT_MAX_GROUPS,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    **Parent mode.** Returns bounded group-by pages for the requested parents.

    :param view_handler: The view handler used to fetch each group page.
    :param base_queryset: The filtered/searched rows queryset to group.
    :param view_group_bys: The view group-by configuration rows.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param parent_requests: The requested parent page dicts.
    :param include_descendants: Whether to recursively enqueue first child pages.
    :param descendant_limit: The maximum number of groups to return per descendant
        page.
    :param total_group_limit: The maximum number of groups to return across all
        returned pages.
    :return: A tuple containing the collected pages and whether the response was
        truncated by a cap.
    """

    total_group_limit = min(total_group_limit, GROUP_BY_DATA_DESCENDANT_MAX_GROUPS)
    pages = []
    pending = list(parent_requests)
    pending_index = 0
    seen = set()
    group_count = 0
    truncated = False

    while pending_index < len(pending):
        if (
            len(pages) >= GROUP_BY_DATA_DESCENDANT_MAX_PAGES
            or group_count >= total_group_limit
        ):
            truncated = True
            break

        parent_request = pending[pending_index]
        pending_index += 1
        parent = parent_request["parent"]
        offset = parent_request["offset"]
        limit = parent_request["limit"]
        parent_row_offset = parent_request.get("parent_row_offset")
        request_key = group_by_data_page_request_key(
            parent, group_by_fields, offset, limit
        )
        if request_key in seen:
            continue
        seen.add(request_key)

        page = view_handler.get_group_by_data(
            base_queryset,
            view_group_bys,
            parent_path=parent,
            offset=offset,
            limit=limit,
            parent_row_offset=parent_row_offset,
        )
        remaining_group_count = total_group_limit - group_count
        page_groups = page.get("groups", [])
        if len(page_groups) > remaining_group_count:
            page = {
                **page,
                "groups": page_groups[:remaining_group_count],
            }
            page_groups = page["groups"]
            truncated = True
        group_count += len(page_groups)
        page["parent"] = parent
        pages.append(page)

        if truncated or not include_descendants:
            continue

        for group in page_groups:
            if group.get("children_count", 0) <= 0:
                continue
            pending.append(
                {
                    "parent": group["path"],
                    "offset": 0,
                    "limit": descendant_limit,
                    "parent_row_offset": group["row_offset"],
                }
            )

    return pages, truncated


def build_group_by_data_response(
    view_handler: ViewHandler,
    request: Request,
    queryset: QuerySet,
    view_group_bys: List[ViewGroupBy],
    group_by_fields: List[Field],
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
    :return: The serialized group-by data response.
    """

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
            pages, truncated = get_group_by_data_pages(
                view_handler,
                queryset,
                view_group_bys,
                group_by_fields,
                parent_requests,
                include_descendants=include_descendants,
                descendant_limit=descendant_limit,
                total_group_limit=(
                    limit
                    if include_descendants
                    else GROUP_BY_DATA_DESCENDANT_MAX_GROUPS
                ),
            )

    return serialize_group_by_data_pages(pages, group_by_fields, truncated=truncated)
