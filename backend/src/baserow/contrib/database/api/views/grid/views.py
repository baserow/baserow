from decimal import Decimal

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    allowed_includes,
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.api.search.serializers import SearchQueryParamSerializer
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.database.api.constants import (
    ADHOC_FILTERS_API_PARAMS,
    ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
    ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION,
    ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION_NO_COMBINE,
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
    ERROR_FIELD_NOT_IN_TABLE,
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
from baserow.contrib.database.api.utils import get_include_exclude_field_ids
from baserow.contrib.database.api.views.errors import (
    ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST,
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.grid.serializers import (
    GridViewFieldOptionsSerializer,
)
from baserow.contrib.database.api.views.serializers import FieldOptionsField
from baserow.contrib.database.api.views.utils import (
    get_public_view_authorization_token,
    get_public_view_filtered_queryset,
    get_view_filtered_queryset,
    paginate_and_serialize_queryset,
    serialize_group_by_fields_metadata,
    serialize_rows_metadata,
    serialize_view_field_options,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    FieldNotInTable,
    FilterFieldNotFound,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.views.exceptions import (
    AggregationTypeDoesNotExist,
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.registries import (
    view_aggregation_type_registry,
    view_type_registry,
)
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.utils import split_comma_separated_string

from .errors import ERROR_GRID_DOES_NOT_EXIST
from .schemas import (
    field_aggregation_response_schema,
    field_aggregations_response_schema,
)
from .serializers import GridViewFilterSerializer


def get_available_aggregation_type():
    return [f.type for f in view_aggregation_type_registry.get_all()]


class GridViewView(APIView):
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
        tags=["Database table grid view"],
        operation_id="list_database_table_grid_view_rows",
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
        ),
        responses={
            200: get_example_pagination_serializer_class(
                get_example_row_serializer_class(
                    example_type="get", user_field_names=False
                ),
                additional_fields={
                    "field_options": FieldOptionsField(
                        serializer_class=GridViewFieldOptionsSerializer, required=False
                    ),
                    "row_metadata": get_example_multiple_rows_metadata_serializer(),
                },
                serializer_name="PaginationSerializerWithGridViewFieldOptions",
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
                ["ERROR_GRID_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
        }
    )
    @allowed_includes("field_options", "row_metadata")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(self, request, view_id, field_options, row_metadata, query_params):
        """
        Lists all the rows of a grid view, paginated either by a page or offset/limit.
        If the limit get parameter is provided the limit/offset pagination will be used
        else the page number pagination.

        Optionally the field options can also be included in the response if the
        `field_options` are provided in the include GET parameter.
        """

        include_fields = request.GET.get("include_fields")
        exclude_fields = request.GET.get("exclude_fields")
        adhoc_filters = AdHocFilters.from_request(request)
        order_by = request.GET.get("order_by")

        view_handler = ViewHandler()
        view = view_handler.get_view_as_user(
            request.user,
            view_id,
            GridView,
            base_queryset=GridView.objects.prefetch_related(
                "viewsort_set", "viewgroupby_set"
            ),
        )
        view_type = view_type_registry.get_by_model(view)

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ListRowsDatabaseTableOperationType.type,
            workspace=workspace,
            context=view.table,
        )
        field_ids = get_include_exclude_field_ids(
            view.table, include_fields, exclude_fields
        )

        queryset = get_view_filtered_queryset(
            request.user, view, adhoc_filters, order_by, query_params
        )
        model = queryset.model

        if ONLY_COUNT_API_PARAM.name in request.GET:
            return Response({"count": queryset.count()})

        response, page, _ = paginate_and_serialize_queryset(
            queryset, request, field_ids
        )

        if view_type.can_group_by and view.viewgroupby_set.all():
            group_by_fields = [
                model._field_objects[group_by.field_id]["field"]
                for group_by in view.viewgroupby_set.all()
            ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)

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

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=False,
                description="Returns only rows that belong to the related view's "
                "table.",
            )
        ],
        tags=["Database table grid view"],
        operation_id="filter_database_table_grid_view_rows",
        description=(
            "Lists only the rows and fields that match the request. Only the rows "
            "with the ids that are in the `row_ids` list are going to be returned. "
            "Same goes for the fields, only the fields with the ids in the "
            "`field_ids` are going to be returned. This endpoint could be used to "
            "refresh data after changes something. For example in the web frontend "
            "after changing a field type, the data of the related cells will be "
            "refreshed using this endpoint. In the example all field types are listed, "
            "but normally  the number in field_{id} key is going to be the id of the "
            "field. The value is what the user has provided and the format of it "
            "depends on the fields type."
        ),
        request=GridViewFilterSerializer,
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=False
            )(many=True),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_GRID_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
        }
    )
    @validate_body(GridViewFilterSerializer)
    def post(self, request, view_id, data):
        """
        Row filter endpoint that only lists the requested rows and optionally only the
        requested fields.
        """

        view = ViewHandler().get_view_as_user(request.user, view_id, GridView)
        CoreHandler().check_permissions(
            request.user,
            ListRowsDatabaseTableOperationType.type,
            workspace=view.table.database.workspace,
            context=view.table,
        )

        model = view.table.get_model(field_ids=data["field_ids"])
        results = model.objects.filter(pk__in=data["row_ids"])

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True
        )
        serializer = serializer_class(results, many=True)
        return Response(serializer.data)


class GridViewFieldAggregationsView(APIView):
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
                description="Select the view you want the aggregations for.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "If provided the aggregations are calculated only for matching "
                    "rows."
                ),
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "if `include` is set to `total`, the total row count will be "
                    "returned with the result."
                ),
            ),
            *ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION_NO_COMBINE,
            SEARCH_MODE_API_PARAM,
        ],
        tags=["Database table grid view"],
        operation_id="get_database_table_grid_view_field_aggregations",
        description=(
            "Returns all field aggregations values previously defined for this grid "
            "view. If filters exist for this view, the aggregations are computed only "
            "on filtered rows."
            "You need to have read permissions on the view to request aggregations."
        ),
        responses={
            200: field_aggregations_response_schema,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_GRID_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
        }
    )
    @allowed_includes("total")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(self, request, view_id, total, query_params):
        """
        Returns the aggregation values for the specified view considering the filters
        and the search term defined for this grid view.
        Also returns the total count to be able to make percentage on client side if
        asked.
        """

        adhoc_filters = AdHocFilters.from_request(request)
        search = query_params.get("search")
        search_mode = query_params.get("search_mode")
        view_handler = ViewHandler()
        view = view_handler.get_view(view_id, GridView)

        # Compute aggregation
        # Note: we can't optimize model by giving a model with just
        # the aggregated field because we may need other fields for filtering
        result = view_handler.get_view_field_aggregations(
            request.user,
            view,
            with_total=total,
            search=search,
            search_mode=search_mode,
            adhoc_filters=adhoc_filters,
        )

        # Decimal("NaN") can't be serialized, therefore we have to replace it
        # with its literal string representation
        nan_replacement_value = "NaN"
        for field in result:
            if isinstance(result[field], Decimal) and result[field].is_nan():
                result[field] = nan_replacement_value

        return Response(result)


class PublicGridViewFieldAggregationsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Select the view you want the aggregations for.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "If provided the aggregations are calculated only for matching "
                    "rows."
                ),
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "if `include` is set to `total`, the total row count will be "
                    "returned with the result."
                ),
            ),
            *ADHOC_FILTERS_API_PARAMS_WITH_AGGREGATION,
            SEARCH_MODE_API_PARAM,
        ],
        tags=["Database table grid view"],
        operation_id="get_database_table_public_grid_view_field_aggregations",
        description=(
            "Returns all field aggregations values previously defined for this grid "
            "view. If filters exist for this view, the aggregations are computed only "
            "on filtered rows."
        ),
        responses={
            200: field_aggregations_response_schema,
            400: get_error_schema(
                [
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(
                [
                    "ERROR_GRID_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
        }
    )
    @allowed_includes("total")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(self, request, slug, total, query_params):
        """
        Returns the aggregation values for the specified view considering the filters
        and the search term defined for this grid view.
        Also returns the total count to be able to make percentage on client side if
        asked.
        """

        adhoc_filters = AdHocFilters.from_request(request)
        search = query_params.get("search")
        search_mode = query_params.get("search_mode")
        view_handler = ViewHandler()
        authorization_token = get_public_view_authorization_token(request)
        view = view_handler.get_public_view_by_slug(
            request.user, slug, GridView, authorization_token=authorization_token
        )

        # Compute aggregation
        # Note: we can't optimize model by giving a model with just
        # the aggregated field because we may need other fields for filtering
        result = view_handler.get_view_field_aggregations(
            request.user,
            view,
            with_total=total,
            search=search,
            search_mode=search_mode,
            adhoc_filters=adhoc_filters,
            combine_filters=True,
            skip_perm_check=True,
        )

        # Decimal("NaN") can't be serialized, therefore we have to replace it
        # with its literal string representation
        nan_replacement_value = "NaN"
        for field in result:
            if isinstance(result[field], Decimal) and result[field].is_nan():
                result[field] = nan_replacement_value

        return Response(result)


class GridViewFieldAggregationView(APIView):
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
                description="Select the view you want the aggregation for.",
            ),
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The field id you want to aggregate",
            ),
            OpenApiParameter(
                name="type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "The aggregation type you want. Available aggregation types: "
                )
                + ", ".join(get_available_aggregation_type()),
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "if `include` is set to `total`, the total row count will be "
                    "returned with the result."
                ),
            ),
        ],
        tags=["Database table grid view"],
        operation_id="get_database_table_grid_view_field_aggregation",
        description=(
            "Computes the aggregation of all the values for a specified field from the "
            "selected grid view. You must select the aggregation type by setting "
            "the `type` GET parameter. If filters are configured for the selected "
            "view, the aggregation is calculated only on filtered rows. "
            "You need to have read permissions on the view to request an aggregation."
        ),
        responses={
            200: field_aggregation_response_schema,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST",
                    "ERROR_FIELD_NOT_IN_TABLE",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_FIELD_DOES_NOT_EXIST",
                    "ERROR_GRID_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            AggregationTypeDoesNotExist: ERROR_AGGREGATION_TYPE_DOES_NOT_EXIST,
        }
    )
    @allowed_includes("total")
    def get(self, request, view_id, field_id, total):
        """
        Returns the aggregation value for the specified view/field considering
        the filters configured for this grid view.
        Also returns the total count to be able to make percentage on client side if
        asked.
        """

        view_handler = ViewHandler()
        view = view_handler.get_view(view_id, GridView)

        field_instance = FieldHandler().get_field(field_id)

        aggregation_type = request.GET.get("type")

        # Compute aggregation
        # Note: we can't optimize model by giving a model with just
        # the aggregated field because we may need other fields for filtering
        aggregations = view_handler.get_field_aggregations(
            request.user, view, [(field_instance, aggregation_type)], with_total=total
        )

        result = {
            "value": aggregations[field_instance.db_column],
        }

        if total:
            result["total"] = aggregations["total"]

        return Response(result)


class PublicGridViewRowsView(APIView):
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
            EXCLUDE_COUNT_API_PARAM,
            *PAGINATION_API_PARAMS,
            ADHOC_SORTING_API_PARAM,
            INCLUDE_FIELDS_API_PARAM,
            EXCLUDE_FIELDS_API_PARAM,
            SEARCH_VALUE_API_PARAM,
            SEARCH_MODE_API_PARAM,
            *ADHOC_FILTERS_API_PARAMS,
            LIMIT_LINKED_ITEMS_API_PARAM,
            OpenApiParameter(
                name="group_by",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Optionally the rows can be grouped by provided field ids "
                "separated by comma. By default no groups are applied. This doesn't "
                "actually responds with the rows groups, this is just what's needed "
                "for the Baserow group by feature.",
            ),
        ],
        tags=["Database table grid view"],
        operation_id="public_list_database_table_grid_view_rows",
        description=(
            "Lists the requested rows of the view's table related to the provided "
            "`slug` if the grid view is public."
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
                        serializer_class=GridViewFieldOptionsSerializer, required=False
                    ),
                },
                serializer_name="PublicPaginationSerializerWithGridViewFieldOptions",
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
                ["ERROR_GRID_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_GRID_DOES_NOT_EXIST,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
        }
    )
    @allowed_includes("field_options")
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(
        self, request: Request, slug: str, field_options: bool, query_params
    ) -> Response:
        """
        Lists all the rows of a grid view, paginated either by a page or offset/limit.
        If the limit get parameter is provided the limit/offset pagination will be used
        else the page number pagination.

        Optionally the field options can also be included in the response if the the
        `field_options` are provided in the include GET parameter.
        """

        view_handler = ViewHandler()
        view = view_handler.get_public_view_by_slug(
            request.user,
            slug,
            GridView,
            authorization_token=get_public_view_authorization_token(request),
        )

        (
            queryset,
            field_ids,
            publicly_visible_field_options,
        ) = get_public_view_filtered_queryset(view, request, query_params)
        model = queryset.model

        if ONLY_COUNT_API_PARAM.name in request.GET:
            return Response({"count": queryset.count()})

        response, page, _ = paginate_and_serialize_queryset(
            queryset, request, field_ids
        )

        if field_options:
            context = {"field_options": publicly_visible_field_options}
            public_view_field_options = serialize_view_field_options(
                view, model, create_if_missing=False, context=context
            )
            response.data.update(**public_view_field_options)

        group_by = request.GET.get("group_by")
        if group_by:
            group_by_fields = [
                # We can safely do this without having to check whether the
                # `group_by` input is valid because this has already been validated
                # by the `get_public_rows_queryset_and_field_ids`.
                model._field_objects[get_field_id_from_field_key(field_string, False)][
                    "field"
                ]
                for field_string in split_comma_separated_string(group_by)
            ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page
            )

            response.data.update(group_by_metadata=serialized_group_by_metadata)

        return response
