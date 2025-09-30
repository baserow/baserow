# When entities are exposed publicly to anonymous users as many entity ids are hardcoded
# to this value as possible to prevent data leaks.
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from baserow.contrib.database.search.handler import SearchMode
from baserow.contrib.database.views.registries import view_filter_type_registry

PUBLIC_PLACEHOLDER_ENTITY_ID = 0
SEARCH_MODE_API_PARAM = OpenApiParameter(
    name="search_mode",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.STR,
    description=(
        "If provided, allows API consumers to determine what kind of search "
        "experience they wish to have. "
        f"If the default `{SearchMode.FT_WITH_COUNT}` is used, then Postgres "
        f"full-text search is used. If `{SearchMode.COMPAT}` is "
        "provided then the search term will be exactly searched for including "
        "whitespace on each cell. This is the Baserow legacy search behaviour."
    ),
)

SEARCH_VALUE_API_PARAM = OpenApiParameter(
    name="search",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.STR,
    description="If provided only rows with data that matches the search "
    "query are going to be returned.",
)

ONLY_COUNT_API_PARAM = OpenApiParameter(
    name="count",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.BOOL,
    description="If provided only the count will be returned.",
)

EXCLUDE_COUNT_API_PARAM = OpenApiParameter(
    name="exclude_count",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.BOOL,
    description=(
        "If provided, the count, previous, and next properties will be excluded from "
        "the response. This is useful for large datasets where counting the total "
        "number of results is slow."
    ),
)
INCLUDE_OPERATION_METADATA = OpenApiParameter(
    name="include_metadata",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.BOOL,
    description=(
        "if provided, this will include `metadata` key containing operation metadata"
        " information in the response. Metadata will include a list of field ids, that"
        " were changed during the operation. The list will be stored in"
        " `update_field_ids` key in `metadata` object. Also, metadata object will"
        " include `cascade_update` key with a list of rows updated in cascade, and"
        " a list of field ids that were updated in cascade update."
    ),
)


def get_filters_object_description(combine_filters=True, view_is_aggregating=False):
    return (
        (
            "A JSON serialized string containing the filter tree to apply "
            "for the aggregation. The filter tree is a nested structure "
            "containing the filters that need to be applied. \n\n"
            if view_is_aggregating
            else "A JSON serialized string containing the filter tree to "
            "apply to this view. The filter tree is a nested structure "
            "containing the filters that need to be applied. \n\n"
        )
        + "An example of a valid filter tree is the following:"
        '`{"filter_type": "AND", "filters": [{"field": 1, "type": "equal", '
        '"value": "test"}]}`. The `field` value must be the ID of the '
        "field to filter on, or the name of the field if "
        "`user_field_names` is true.\n\n"
        f"The following filters are available: "
        f'{", ".join(view_filter_type_registry.get_types())}.'
        "\n\n**Please note that if this parameter is provided, all other "
        "`filter__{field}__{filter}` will be ignored, "
        "as well as the `filter_type` parameter.**"
        + (
            "\n\n**Please note that by passing the filters parameter the "
            "view filters saved for the view itself will be ignored.**"
            if not combine_filters
            else ""
        )
    )


def make_adhoc_filter_api_params(combine_filters=True, view_is_aggregating=False):
    """
    Generate OpenAPI parameters for adhoc filter API params.

    This function generates a parameter set with normalized descriptions. Note, that
    there is a variance between views in semantics of adhoc filtering params.

    A public view usually allows to combine saved view filters and adhoc filters.
    Non-public views usually use saved filters if no adhoc filter is provided in
    request's query string.

    A view that returns aggregated values use filtering params differently, which is
    reflected in descriptions.

    :param combine_filters: if not set, adds a line about superseding saved view
        filters with adhoc filters
    :param view_is_aggregating: if set, describe filtering params as aggregation
        filtering parameters
    :return:
    """

    values = (
        OpenApiParameter(
            name="filters",
            location=OpenApiParameter.QUERY,
            type=OpenApiTypes.STR,
            description=lazy(
                lambda: get_filters_object_description(
                    combine_filters, view_is_aggregating
                ),
                str,
            )(),
        ),
        OpenApiParameter(
            name="filter__{field}__{filter}",
            location=OpenApiParameter.QUERY,
            type=OpenApiTypes.STR,
            description=lazy(
                lambda: (
                    (
                        f"The aggregation can optionally be filtered by the same view "
                        f"filters available for the views. Multiple filters can be "
                        f"provided if they follow the same format. The field and "
                        f"filter variable indicate how to filter and the value "
                        f"indicates where to filter on.\n\n"
                        if view_is_aggregating
                        else f"The rows can optionally be filtered by the same view "
                        f"filters available for the views. Multiple filters can be "
                        f"provided if they follow the same format. The field and "
                        f"filter variable indicate how to filter and the value "
                        f"indicates where to filter on.\n\n"
                    )
                    + f"For example if you provide the following GET parameter "
                    f"`filter__field_1__equal=test` then only rows where the value of "
                    f"field_1 is equal to test are going to be returned.\n\n"
                    f"The following filters are available: "
                    f'{", ".join(view_filter_type_registry.get_types())}.'
                    "\n\n**Please note that if the `filters` parameter is provided, "
                    "this parameter will be ignored.** \n\n"
                    + (
                        "\n\n**Please note that by passing the filter parameters the "
                        "view filters saved for the view itself will be ignored.**"
                        if not combine_filters
                        else ""
                    )
                ),
                str,
            )(),
        ),
        OpenApiParameter(
            name="filter_type",
            location=OpenApiParameter.QUERY,
            type=OpenApiTypes.STR,
            description=(
                (
                    "`AND`: Indicates that the aggregated rows must match all the "
                    "provided filters.\n\n"
                    "`OR`: Indicates that the aggregated rows only have to match one "
                    "of the filters.\n\n"
                    if view_is_aggregating
                    else "`AND`: Indicates that the rows must match all the provided "
                    "filters.\n\n"
                    "`OR`: Indicates that the rows only have to match one of the "
                    "filters.\n\nThis works only if two or more filters are provided."
                    "\n\n**Please note that if the `filters` parameter is provided, "
                    "this parameter will be ignored.**"
                )
            ),
        ),
    )
    return values


# views that allow for saved and adhoc filters combination:
# RowsView, PublicGalleryViewRowsView, PublicGridViewRowsView, PublicCalendarViewView,
# PublicKanbanViewView, PublicTimelineViewRowsView
ADHOC_FILTERS_API_PARAMS = make_adhoc_filter_api_params(
    combine_filters=True, view_is_aggregating=False
)

# views that will use saved view filters only if no adhoc filters are present:
# GalleryViewView, GridViewView, CalendarViewView, KanbanViewView, TimelineViewView
ADHOC_FILTERS_API_PARAMS_NO_COMBINE = make_adhoc_filter_api_params(
    combine_filters=False, view_is_aggregating=False
)

# PublicGridViewFieldAggregationsView
ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION = make_adhoc_filter_api_params(
    combine_filters=True, view_is_aggregating=True
)

# GridViewFieldAggregationsView
ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION_NO_COMBINE = make_adhoc_filter_api_params(
    combine_filters=False, view_is_aggregating=True
)

ADHOC_SORTING_API_PARAM = OpenApiParameter(
    name="order_by",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.STR,
    description="Optionally the rows can be ordered by provided field ids "
    "separated by comma. By default a field is ordered in ascending (A-Z) "
    "order, but by prepending the field with a '-' it can be ordered "
    "descending (Z-A).",
)

PAGINATION_API_PARAMS = (
    OpenApiParameter(
        name="limit",
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.INT,
        description="Defines how many rows should be returned.",
    ),
    OpenApiParameter(
        name="offset",
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.INT,
        description="Can only be used in combination with the `limit` "
        "parameter and defines from which offset the rows should "
        "be returned.",
    ),
    OpenApiParameter(
        name="page",
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.INT,
        description="Defines which page of rows should be returned. Either "
        "the `page` or `limit` can be provided, not both.",
    ),
    OpenApiParameter(
        name="size",
        location=OpenApiParameter.QUERY,
        type=OpenApiTypes.INT,
        description="Can only be used in combination with the `page` parameter "
        "and defines how many rows should be returned.",
    ),
)

INCLUDE_FIELDS_API_PARAM = OpenApiParameter(
    name="include_fields",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.STR,
    description=(
        "All the fields are included in the response by default. You can "
        "select a subset of fields by providing the fields query "
        "parameter. If you for example provide the following GET "
        "parameter `include_fields=field_1,field_2` then only the fields "
        "with id `1` and id `2` are going to be selected and included in "
        "the response."
    ),
)

EXCLUDE_FIELDS_API_PARAM = OpenApiParameter(
    name="exclude_fields",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.STR,
    description=(
        "All the fields are included in the response by default. You can "
        "select a subset of fields by providing the exclude_fields query "
        "parameter. If you for example provide the following GET "
        "parameter `exclude_fields=field_1,field_2` then the fields with "
        "id `1` and id `2` are going to be excluded from the selection and "
        "response. "
    ),
)

LIMIT_LINKED_ITEMS_API_PARAM = OpenApiParameter(
    name="limit_linked_items",
    location=OpenApiParameter.QUERY,
    type=OpenApiTypes.INT,
    description=(
        "if provided, the maximum number of relationships per link row field "
        "in the response. If not provided, all the relationships will be returned."
    ),
)
