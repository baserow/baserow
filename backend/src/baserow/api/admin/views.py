from typing import Dict, List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import (
    ERROR_INVALID_SORT_ATTRIBUTE,
    ERROR_INVALID_SORT_DIRECTION,
)
from baserow.api.exceptions import (
    InvalidSortAttributeException,
    InvalidSortDirectionException,
    QueryParameterValidationException,
)
from baserow.api.mixins import (
    FilterableViewMixin,
    SearchableViewMixin,
    SortableViewMixin,
)
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.core.utils import split_comma_separated_string


class APIListingView(
    APIView, SearchableViewMixin, SortableViewMixin, FilterableViewMixin
):
    serializer_class = None
    pagination_class = PageNumberPagination
    search_fields: List[str] = ["id"]
    filters_field_mapping: Dict[str, str] = {}
    sort_field_mapping: Dict[str, str] = {}

    @map_exceptions(
        {
            InvalidSortDirectionException: ERROR_INVALID_SORT_DIRECTION,
            InvalidSortAttributeException: ERROR_INVALID_SORT_ATTRIBUTE,
        }
    )
    def get(self, request):
        """
        Responds with paginated results related to queryset and the serializer
        defined on this class.
        """

        search = request.GET.get("search")
        sorts = request.GET.get("sorts")
        ids_param = request.GET.get("ids")

        queryset = self.get_queryset(request)
        queryset = self.apply_filters(request.GET, queryset)
        queryset = self.apply_search(search, queryset)
        queryset = self.apply_sorts_or_default_sort(sorts, queryset)
        queryset = self.apply_ids_filter(ids_param, queryset)

        paginator = self.pagination_class(limit_page_size=100)
        page = paginator.paginate_queryset(queryset, request, self)
        serializer = self.get_serializer(request, page, many=True)

        return paginator.get_paginated_response(serializer.data)

    def get_queryset(self, request):
        raise NotImplementedError("The get_queryset method must be set.")

    def apply_ids_filter(self, ids_param, queryset):
        if not ids_param:
            return queryset

        record_ids = split_comma_separated_string(ids_param)

        invalid_id = next(
            (record for record in record_ids if not record.isdigit()), None
        )
        if invalid_id is not None:
            raise QueryParameterValidationException(
                {
                    "ids": [
                        {
                            "code": "invalid",
                            "error": f"'{invalid_id}' is not a valid ID. Only positive "
                            f"integers are accepted.",
                        }
                    ]
                }
            )

        return queryset.filter(id__in=[int(record_id) for record_id in record_ids])

    def get_serializer(self, request, *args, **kwargs):
        if not self.serializer_class:
            raise NotImplementedError(
                "Either the serializer_class must be set or the get_serializer method "
                "must be overwritten."
            )

        return self.serializer_class(*args, **kwargs)

    @staticmethod
    def get_extend_schema_parameters(
        name, serializer_class, search_fields, sort_field_mapping, extra_parameters=None
    ):
        """
        Returns the schema properties that can be used in in the @extend_schema
        decorator.
        """

        parameters = []
        if search_fields:
            parameters.append(
                OpenApiParameter(
                    name="search",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.STR,
                    description=f"If provided only {name} with {' or '.join(search_fields)} "
                    "that match the query will be returned.",
                )
            )

        if sort_field_mapping:
            fields = sort_field_mapping.keys()
            all_fields = ", ".join(fields)
            field_name_1 = "field_1"
            field_name_2 = "field_2"
            for i, field in enumerate(fields):
                if i == 0:
                    field_name_1 = field
                if i == 1:
                    field_name_2 = field

            parameters.append(
                OpenApiParameter(
                    name="sorts",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.STR,
                    description=f"A comma separated string of attributes to sort by, "
                    f"each attribute must be prefixed with `+` for a descending "
                    f"sort or a `-` for an ascending sort. The accepted attribute "
                    f"names are: `{all_fields}`. For example `sorts=-{field_name_1},"
                    f"-{field_name_2}` will sort the {name} first by descending "
                    f"{field_name_1} and then ascending {field_name_2}. A sort"
                    f"parameter with multiple instances of the same sort attribute "
                    f"will respond with the ERROR_INVALID_SORT_ATTRIBUTE "
                    f"error.",
                ),
            )

        return {
            "parameters": [
                *parameters,
                OpenApiParameter(
                    name="page",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.INT,
                    description="Defines which page should be returned.",
                ),
                OpenApiParameter(
                    name="size",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.INT,
                    description=f"Defines how many {name} should be returned per page.",
                ),
                OpenApiParameter(
                    name="ids",
                    location=OpenApiParameter.QUERY,
                    type=OpenApiTypes.STR,
                    description=f"A comma-separated list of {name} IDs to filter by. "
                    f"When provided, only {name} with those IDs are returned.",
                ),
                *(extra_parameters or []),
            ],
            "responses": {
                200: get_example_pagination_serializer_class(serializer_class),
                400: get_error_schema(
                    [
                        "ERROR_PAGE_SIZE_LIMIT",
                        "ERROR_INVALID_SORT_DIRECTION",
                        "ERROR_INVALID_SORT_ATTRIBUTE",
                    ]
                ),
                401: None,
            },
        }


class AdminListingView(APIListingView):
    permission_classes = (IsAdminUser,)
