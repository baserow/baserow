from baserow_premium.api.views.timeline.errors import (
    ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS,
)
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.views.exceptions import TimelineViewHasInvalidDateSettings
from baserow_premium.views.handler import (
    get_public_timeline_view_filtered_queryset,
    get_timeline_view_filtered_queryset,
)
from baserow_premium.views.models import TimelineView
from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    ADHOC_SORTING_API_PARAM,
    EXCLUDE_COUNT_API_PARAM,
    EXCLUDE_FIELDS_API_PARAM,
    INCLUDE_FIELDS_API_PARAM,
    LIMIT_LINKED_ITEMS_API_PARAM,
    ONLY_COUNT_API_PARAM,
    PAGINATION_API_PARAMS,
    SEARCH_MODE_API_PARAM,
    SEARCH_VALUE_API_PARAM,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FILTER_FIELD_NOT_FOUND,
    ERROR_INCOMPATIBLE_FIELD,
    ERROR_ORDER_BY_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
)
from baserow.contrib.database.api.rows.serializers import (
    get_example_multiple_rows_metadata_serializer,
    get_example_row_serializer_class,
)
from baserow.contrib.database.api.utils import get_include_exclude_field_ids
from baserow.contrib.database.api.views.errors import (
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.serializers import FieldOptionsField
from baserow.contrib.database.api.views.utils import (
    get_public_view_authorization_token,
    paginate_and_serialize_queryset,
    serialize_rows_metadata,
    serialize_view_field_options,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    FilterFieldNotFound,
    IncompatibleField,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from .errors import ERROR_TIMELINE_DOES_NOT_EXIST
from .serializers import TimelineViewFieldOptionsSerializer


class TimelineViewView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only rows that belong to the related view's "
                "table.",
            ),
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
            ONLY_COUNT_API_PARAM,
            EXCLUDE_COUNT_API_PARAM,
            *PAGINATION_API_PARAMS,
            *ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
            ADHOC_SORTING_API_PARAM,
            INCLUDE_FIELDS_API_PARAM,
            EXCLUDE_FIELDS_API_PARAM,
            SEARCH_VALUE_API_PARAM,
            SEARCH_MODE_API_PARAM,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table timeline view"],
        operation_id="list_database_table_timeline_view_rows",
        description=(
            "Lists the requested rows of the view's table related to the provided "
            "`view_id` if the authorized user has access to the database's workspace. "
            "The response is paginated either by a limit/offset or page/size style. "
            "The style depends on the provided GET parameters. The properties of the "
            "returned rows depends on which fields the table has. For a complete "
            "overview of fields use the **list_database_table_fields** endpoint to "
            "list them all. In the example all field types are listed, but normally "
            "the number in field_{id} key is going to be the id of the field. "
            "The value is what the user has provided and the format of it depends on "
            "the fields type.\n"
            "\n"
            "The filters and sortings are automatically applied. To get a full "
            "overview of the applied filters and sortings you can use the "
            "`list_database_table_view_filters` and "
            "`list_database_table_view_sortings` endpoints."
            "\n\nThis is a **premium** feature."
        ),
        responses={
            200: get_example_pagination_serializer_class(
                get_example_row_serializer_class(
                    example_type="get", user_field_names=False
                ),
                additional_fields={
                    "field_options": FieldOptionsField(
                        serializer_class=TimelineViewFieldOptionsSerializer,
                        required=False,
                    ),
                    "row_metadata": get_example_multiple_rows_metadata_serializer(),
                },
                serializer_name="PaginationSerializerWithTimelineViewFieldOptions",
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            404: get_error_schema(
                ["ERROR_TIMELINE_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_TIMELINE_DOES_NOT_EXIST,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            TimelineViewHasInvalidDateSettings: ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS,
            IncompatibleField: ERROR_INCOMPATIBLE_FIELD,
        }
    )
    @allowed_includes("field_options", "row_metadata")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(self, request, view_id, field_options, row_metadata, query_params):
        """
        Lists all the rows of a timeline view, paginated either by a page or
        offset/limit. If the limit get parameter is provided the limit/offset pagination
        will be used else the page number pagination.

        Optionally the field options can also be included in the response if the
        `field_options` are provided in the include GET parameter.
        """

        include_fields = request.GET.get("include_fields")
        exclude_fields = request.GET.get("exclude_fields")
        adhoc_filters = AdHocFilters.from_request(request)
        order_by = request.GET.get("order_by")

        view_handler = ViewHandler()
        base_queryset = TimelineView.objects.select_related(
            "start_date_field", "end_date_field"
        ).prefetch_related("viewsort_set")

        view: TimelineView = view_handler.get_view_as_user(
            request.user, view_id, TimelineView, base_queryset=base_queryset
        )
        workspace = view.table.database.workspace

        # We don't want to check if there is an active premium license if the workspace
        # is a template because that feature must then be available for demo purposes.
        if not workspace.has_template():
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, request.user, workspace
            )

        CoreHandler().check_permissions(
            request.user,
            ListRowsDatabaseTableOperationType.type,
            workspace=workspace,
            context=view.table,
        )

        field_ids = get_include_exclude_field_ids(
            view.table, include_fields, exclude_fields
        )

        queryset = get_timeline_view_filtered_queryset(
            request.user, view, adhoc_filters, order_by, query_params
        )
        model = queryset.model

        if ONLY_COUNT_API_PARAM.name in request.GET:
            return Response({"count": queryset.count()})

        response, page, _ = paginate_and_serialize_queryset(
            queryset, request, field_ids
        )

        if field_options:
            response.data.update(**serialize_view_field_options(view, model))

        if row_metadata:
            response.data.update(
                row_metadata=serialize_rows_metadata(request.user, view, page)
            )

        view_loaded.send(
            sender=self,
            table=view.table,
            view=view,
            table_model=model,
            user=request.user,
        )
        return response


class PublicTimelineViewRowsView(APIView):
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
            ONLY_COUNT_API_PARAM,
            *PAGINATION_API_PARAMS,
            *ADHOC_FILTERS_API_PARAMS,
            ADHOC_SORTING_API_PARAM,
            INCLUDE_FIELDS_API_PARAM,
            EXCLUDE_FIELDS_API_PARAM,
            SEARCH_VALUE_API_PARAM,
            SEARCH_MODE_API_PARAM,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table timeline view"],
        operation_id="public_list_database_table_timeline_view_rows",
        description=(
            "Lists the requested rows of the view's table related to the provided "
            "`slug` if the timeline view is public."
            "The response is paginated either by a limit/offset or page/size style. "
            "The style depends on the provided GET parameters. The properties of the "
            "returned rows depends on which fields the table has. For a complete "
            "overview of fields use the **list_database_table_fields** endpoint to "
            "list them all. In the example all field types are listed, but normally "
            "the number in field_{id} key is going to be the id of the field. "
            "The value is what the user has provided and the format of it depends on "
            "the fields type.\n\n"
        ),
        responses={
            200: get_example_pagination_serializer_class(
                get_example_row_serializer_class(
                    example_type="get", user_field_names=False
                ),
                additional_fields={
                    "field_options": FieldOptionsField(
                        serializer_class=TimelineViewFieldOptionsSerializer,
                        required=False,
                    ),
                },
                serializer_name="PublicPaginationSerializerWithTimelineViewFieldOptions",
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(
                ["ERROR_TIMELINE_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_TIMELINE_DOES_NOT_EXIST,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
            TimelineViewHasInvalidDateSettings: ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS,
            IncompatibleField: ERROR_INCOMPATIBLE_FIELD,
        }
    )
    @allowed_includes("field_options")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(
        self, request: Request, slug: str, field_options: bool, query_params
    ) -> Response:
        """
        Lists all the rows of a timeline view, paginated either by a page or
        offset/limit. If the limit get parameter is provided the limit/offset pagination
        will be used else the page number pagination.

        Optionally the field options can also be included in the response if the the
        `field_options` are provided in the include GET parameter.
        """

        view_handler = ViewHandler()
        view = view_handler.get_public_view_by_slug(
            request.user,
            slug,
            TimelineView,
            authorization_token=get_public_view_authorization_token(request),
        )

        (
            queryset,
            field_ids,
            publicly_visible_field_options,
        ) = get_public_timeline_view_filtered_queryset(view, request, query_params)
        model = queryset.model

        count = ONLY_COUNT_API_PARAM.name in request.GET
        if count:
            return Response({"count": queryset.count()})

        response, _, _ = paginate_and_serialize_queryset(queryset, request, field_ids)

        if field_options:
            context = {"field_options": publicly_visible_field_options}
            public_view_field_options = serialize_view_field_options(
                view, model, create_if_missing=False, context=context
            )
            response.data.update(**public_view_field_options)

        return response
