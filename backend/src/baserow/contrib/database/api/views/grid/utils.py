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
from collections import defaultdict
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

GROUP_BY_DATA_DESCENDANT_MAX_GROUPS = 2000
# A deep tree legitimately produces many parent pages for a single viewport (one per
# internal group node), so the page cap is only a coarse backstop: the per-level batched
# descent issues one query per level regardless of page count, and the visible-row window
# plus the group cap are what actually bound the work.
GROUP_BY_DATA_DESCENDANT_MAX_PAGES = GROUP_BY_DATA_DESCENDANT_MAX_GROUPS


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
    row_budget: int = GROUP_BY_DATA_DESCENDANT_MAX_GROUPS,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    **Parent mode.** Returns bounded group-by pages for the requested parents.

    When ``include_descendants`` is set, each parent's subtree is walked
    depth-first (pre-order) down to its leaves, so one request returns the whole
    visible subtree. The walk stops once the accumulated leaf ``row_count``
    reaches ``row_budget`` (the visible-viewport size); the leaf that crosses the
    budget is included whole because its rows paginate separately. The page and
    group caps remain as backstops for pathological wide/deep trees, after which
    the rest lazy-loads on scroll.

    :param view_handler: The view handler used to fetch each group page.
    :param base_queryset: The filtered/searched rows queryset to group.
    :param view_group_bys: The view group-by configuration rows.
    :param group_by_fields: The ordered group-by fields configured on the view.
    :param parent_requests: The requested parent page dicts.
    :param include_descendants: Whether to recursively enqueue first child pages.
    :param descendant_limit: The maximum number of groups to return per descendant
        page.
    :param row_budget: The maximum accumulated leaf ``row_count`` to fetch across
        the returned subtree when expanding descendants.
    :return: A tuple containing the collected pages and whether the response was
        truncated by a cap.
    """

    # Direct page requests (no descendants) keep the per-parent path, which fetches each
    # requested page individually and so reports empty pages, their total sibling count,
    # and arbitrary offsets exactly.
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
            )
            page["parent"] = parent
            group_count += len(page.get("groups", []))
            pages.append(page)
        return pages, truncated

    pages = []
    seen = set()
    group_count = 0
    truncated = False

    # Resolve each requested parent's absolute row offset (computing it when the client
    # did not thread it in, so threading stays a pure speedup). The descent only expands
    # groups whose rows start inside ``[start, start + row_budget)`` rather than fanning
    # across the whole breadth of a wide tree.
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
    # Anchor the window where the fetched groups actually start, not at the parent's first
    # row. A scrolled slice (offset > 0) begins deep into the parent, so anchoring on the
    # parent offset would window the top of the tree and expand nothing the user can see.
    window_end = None

    # Group the requested parents by depth (and page slice) so each level is fetched in
    # one batched query covering all of its parents instead of one query per parent.
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
            )

            # Split the batched groups back into one page per parent, making each group's
            # parent-relative ``row_offset`` absolute with its parent's offset.
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

            if window_end is None and page_by_key:
                window_end = row_budget + min(
                    group["row_offset"]
                    for page in page_by_key.values()
                    for group in page["groups"]
                )

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
            # The client sends the row window that fills its screen in one descent,
            # defaulting to the page limit when unset. Clamp to the group cap: a wider
            # window can't surface more than the cap allows.
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
            )

    return serialize_group_by_data_pages(pages, group_by_fields, truncated=truncated)
