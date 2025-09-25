from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    allowed_includes,
    map_exceptions,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.api.search.serializers import SearchQueryParamSerializer
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.database.api.constants import (
    ADHOC_FILTERS_API_PARAMS,
    ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
    EXCLUDE_COUNT_API_PARAM,
    LIMIT_LINKED_ITEMS_API_PARAM,
    ONLY_COUNT_API_PARAM,
    SEARCH_MODE_API_PARAM,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FILTER_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
)
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_example_multiple_rows_metadata_serializer,
    get_example_row_serializer_class,
    get_row_serializer_class,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.gallery.serializers import (
    GalleryViewFieldOptionsSerializer,
)
from baserow.contrib.database.api.views.serializers import FieldOptionsField
from baserow.contrib.database.api.views.utils import (
    get_public_view_authorization_token,
    parse_limit_linked_items_params,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    FilterFieldNotFound,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GalleryView
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from .errors import ERROR_GALLERY_DOES_NOT_EXIST
from .pagination import GalleryLimitOffsetPagination


class GalleryViewView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only rows that belong to the related view's "
                "table.",
            ),
            ONLY_COUNT_API_PARAM,
            EXCLUDE_COUNT_API_PARAM,
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list allowing the values of `field_options` and "
                    "`row_metadata` which will add the object/objects with the same "
                    "name to the response if included. The `field_options` object "
                    "contains user defined view settings for each field. For example "
                    "the field's width is included in here. The `row_metadata` object"
                    " includes extra row specific data on a per row basis."
                ),
            ),
            OpenApiParameter(
                name="order_by",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Optionally the rows can be ordered by provided field ids "
                "separated by comma. By default a field is ordered in ascending (A-Z) "
                "order, but by prepending the field with a '-' it can be ordered "
                "descending (Z-A).",
            ),
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
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided only rows with data that matches the search "
                "query are going to be returned.",
            ),
            *ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
            SEARCH_MODE_API_PARAM,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table gallery view"],
        operation_id="list_database_table_gallery_view_rows",
        description=(
            "Lists the requested rows of the view's table related to the provided "
            "`view_id` if the authorized user has access to the database's workspace. "
            "The response is paginated by a limit/offset style."
        ),
        responses={
            200: get_example_pagination_serializer_class(
                get_example_row_serializer_class(
                    example_type="get", user_field_names=False
                ),
                additional_fields={
                    "field_options": FieldOptionsField(
                        serializer_class=GalleryViewFieldOptionsSerializer,
                        required=False,
                    ),
                    "row_metadata": get_example_multiple_rows_metadata_serializer(),
                },
                serializer_name="PaginationSerializerWithGalleryViewFieldOptions",
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                ]
            ),
            404: get_error_schema(["ERROR_GALLERY_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GALLERY_DOES_NOT_EXIST,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
        }
    )
    @allowed_includes("field_options", "row_metadata")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(
        self,
        request: Request,
        view_id: int,
        field_options: bool,
        row_metadata: bool,
        query_params,
    ):
        """Lists the rows for the gallery view."""

        adhoc_filters = AdHocFilters.from_request(request)

        order_by = request.GET.get("order_by")
        view_handler = ViewHandler()
        view = view_handler.get_view_as_user(
            request.user,
            view_id,
            GalleryView,
            base_queryset=GalleryView.objects.prefetch_related("viewsort_set"),
        )
        view_type = view_type_registry.get_by_model(view)

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ListRowsDatabaseTableOperationType.type,
            workspace=workspace,
            context=view.table,
        )

        search = query_params.get("search")
        search_mode = query_params.get("search_mode")

        model = view.table.get_model()
        queryset = view_handler.get_queryset(
            request.user,
            view,
            search,
            model,
            search_mode=search_mode,
            apply_sorts=order_by is None,
            apply_filters=not adhoc_filters.has_any_filters,
        )

        if adhoc_filters.has_any_filters:
            queryset = adhoc_filters.apply_to_queryset(model, queryset)
        if order_by is not None:
            queryset = queryset.order_by_fields_string(order_by, False)

        if ONLY_COUNT_API_PARAM.name in request.GET:
            return Response({"count": queryset.count()})

        paginator = GalleryLimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request, self)

        limit_linked_items = parse_limit_linked_items_params(request)
        serializer_extra_kwargs = {"limit_linked_items": limit_linked_items}

        serializer_class = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            extra_kwargs=serializer_extra_kwargs,
        )
        serializer = serializer_class(page, many=True)

        response = paginator.get_paginated_response(serializer.data)

        if field_options:
            context = {"fields": [o["field"] for o in model._field_objects.values()]}
            serializer_class = view_type.get_field_options_serializer_class(
                create_if_missing=True
            )
            response.data.update(**serializer_class(view, context=context).data)

        if row_metadata:
            row_metadata = row_metadata_registry.generate_and_merge_metadata_for_rows(
                request.user, view.table, (row.id for row in page)
            )
            response.data.update(row_metadata=row_metadata)

        view_loaded.send(
            sender=self,
            table=view.table,
            view=view,
            table_model=model,
            user=request.user,
        )
        return response


class PublicGalleryViewRowsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Returns only rows that belong to the related view.",
            ),
            OpenApiParameter(
                name="count",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description="If provided only the count will be returned.",
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list allowing the values of "
                    "`field_options` which will add the object/objects with the "
                    "same "
                    "name to the response if included. The `field_options` object "
                    "contains user defined view settings for each field. For "
                    "example the field's width is included in here."
                ),
            ),
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
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided only rows with data that matches the search "
                "query are going to be returned.",
            ),
            OpenApiParameter(
                name="order_by",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Optionally the rows can be ordered by provided field ids "
                "separated by comma. By default a field is ordered in ascending (A-Z) "
                "order, but by prepending the field with a '-' it can be ordered "
                "descending (Z-A).",
            ),
            *ADHOC_FILTERS_API_PARAMS,
            OpenApiParameter(
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
            ),
            OpenApiParameter(
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
            ),
            SEARCH_MODE_API_PARAM,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table gallery view"],
        operation_id="public_list_database_table_gallery_view_rows",
        description=(
            "Lists the requested rows of the view's table related to the provided "
            "`slug` if the gallery view is public."
            "The response is paginated either by a limit/offset or page/size style. "
            "The style depends on the provided GET parameters. The properties of the "
            "returned rows depends on which fields the table has. For a complete "
            "overview of fields use the **list_database_table_fields** endpoint to "
            "list them all. In the example all field types are listed, but normally "
            "the number in field_{id} key is going to be the id of the field. "
            "The value is what the user has provided and the format of it depends on "
            "the fields type.\n"
            "\n"
        ),
        responses={
            200: get_example_pagination_serializer_class(
                get_example_row_serializer_class(
                    example_type="get", user_field_names=False
                ),
                additional_fields={
                    "field_options": FieldOptionsField(
                        serializer_class=GalleryViewFieldOptionsSerializer,
                        required=False,
                    ),
                },
                serializer_name="PublicPaginationSerializerWithGalleryViewFieldOptions",
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(
                ["ERROR_GALLERY_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GALLERY_DOES_NOT_EXIST,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
        }
    )
    @transaction.atomic
    @allowed_includes("field_options")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(
        self, request: Request, slug: str, field_options: bool, query_params
    ) -> Response:
        """
        Lists all the rows of a gallery view, paginated with
        GalleryLimitOffsetPagination.

        Optionally the field options can also be included in the response if the the
        `field_options` are provided in the include GET parameter.
        """

        search = query_params.get("search")
        search_mode = query_params.get("search_mode")
        order_by = request.GET.get("order_by")
        include_fields = request.GET.get("include_fields")
        exclude_fields = request.GET.get("exclude_fields")
        adhoc_filters = AdHocFilters.from_request(request)

        count = "count" in request.GET

        view_handler = ViewHandler()
        view = view_handler.get_public_view_by_slug(
            request.user,
            slug,
            GalleryView,
            authorization_token=get_public_view_authorization_token(request),
        )
        view_type = view_type_registry.get_by_model(view)
        model = view.table.get_model()

        (
            queryset,
            field_ids,
            publicly_visible_field_options,
        ) = ViewHandler().get_public_rows_queryset_and_field_ids(
            view,
            search=search,
            order_by=order_by,
            include_fields=include_fields,
            exclude_fields=exclude_fields,
            adhoc_filters=adhoc_filters,
            table_model=model,
            view_type=view_type,
            search_mode=search_mode,
        )

        if count:
            return Response({"count": queryset.count()})

        paginator = GalleryLimitOffsetPagination()
        page = paginator.paginate_queryset(queryset, request, self)

        limit_linked_items = parse_limit_linked_items_params(request)
        serializer_extra_kwargs = {"limit_linked_items": limit_linked_items}

        serializer_class = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
            extra_kwargs=serializer_extra_kwargs,
        )
        serializer = serializer_class(page, many=True)

        response = paginator.get_paginated_response(serializer.data)

        if field_options:
            context = {"field_options": publicly_visible_field_options}
            serializer_class = view_type.get_field_options_serializer_class(
                create_if_missing=True
            )
            response.data.update(**serializer_class(view, context=context).data)

        return response
