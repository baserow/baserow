from copy import deepcopy
from typing import Any, Dict

from django.conf import settings
from django.core.exceptions import ValidationError

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.decorators import (
    allowed_includes,
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_DATABASE_DEADLOCK, ERROR_USER_NOT_IN_GROUP
from baserow.api.exceptions import (
    QueryParameterValidationException,
    RequestBodyValidationException,
)
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.api.utils import validate_data
from baserow.config.settings.utils import str_to_bool
from baserow.contrib.database.api.constants import (
    ADHOC_FILTERS_API_PARAMS,
    INCLUDE_OPERATION_METADATA,
    SEARCH_MODE_API_PARAM,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_DATA_CONSTRAINT,
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FILTER_FIELD_NOT_FOUND,
    ERROR_INCOMPATIBLE_FIELD_TYPE,
    ERROR_ORDER_BY_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
)
from baserow.contrib.database.api.rows.errors import (
    ERROR_CANNOT_CREATE_ROWS_IN_TABLE,
    ERROR_CANNOT_DELETE_ROWS_IN_TABLE,
    ERROR_INVALID_JOIN_PARAMETER,
    ERROR_ROW_DOES_NOT_EXIST,
    ERROR_ROW_IDS_NOT_UNIQUE,
)
from baserow.contrib.database.api.rows.exceptions import InvalidJoinParameterException
from baserow.contrib.database.api.rows.serializers import (
    GetRowAdjacentSerializer,
    GetRowQueryParamsSerializer,
)
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.api.tokens.authentications import TokenAuthentication
from baserow.contrib.database.api.tokens.errors import (
    ERROR_CANNOT_INCLUDE_ROW_METADATA,
    ERROR_NO_PERMISSION_TO_TABLE,
)
from baserow.contrib.database.api.utils import (
    extract_link_row_joins_from_request,
    extract_send_webhook_events_from_params,
    extract_user_field_names_from_params,
    get_include_exclude_fields,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.utils import serialize_single_row_metadata
from baserow.contrib.database.field_rules.collector import CascadeUpdatedRows
from baserow.contrib.database.fields.exceptions import (
    FieldDataConstraintException,
    FieldDoesNotExist,
    FilterFieldNotFound,
    IncompatibleField,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.actions import (
    CreateRowActionType,
    CreateRowsActionType,
    DeleteRowActionType,
    DeleteRowsActionType,
    MoveRowActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.exceptions import (
    CannotCreateRowsInTable,
    CannotDeleteRowsInTable,
    RowDoesNotExist,
    RowIdsNotUnique,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.history import RowHistoryHandler
from baserow.contrib.database.rows.operations import (
    ReadAdjacentRowDatabaseRowOperationType,
    ReadDatabaseRowHistoryOperationType,
)
from baserow.contrib.database.rows.signals import rows_loaded
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ListRowNamesDatabaseTableOperationType,
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tokens.exceptions import (
    NoPermissionToTable,
    TokenCannotIncludeRowMetadata,
)
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.contrib.database.views.exceptions import (
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.action.registries import action_type_registry
from baserow.core.db import atomic_with_retry_on_deadlock
from baserow.core.exceptions import DeadlockException, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem

from .example_serializers import example_pagination_row_serializer_class
from .schemas import row_names_response_schema
from .serializers import (
    BatchCreateRowsQueryParamsSerializer,
    BatchDeleteRowsQueryParamsSerializer,
    BatchDeleteRowsSerializer,
    BatchUpdateRowsQueryParamsSerializer,
    CreateRowQueryParamsSerializer,
    DeleteRowQueryParamsSerializer,
    ListRowsQueryParamsSerializer,
    MoveRowQueryParamsSerializer,
    RowHistorySerializer,
    RowSerializer,
    UpdateRowQueryParamsSerializer,
    get_batch_row_serializer_class,
    get_example_batch_rows_serializer_class,
    get_example_row_serializer_class,
    get_row_serializer_class,
)


def build_response_with_metadata(
    rows,
    request,
    model,
    serializer_class,
    updated_field_ids: list | None = None,
    cascade_update: CascadeUpdatedRows | None = None,
) -> Response:
    """
    Helper to build view's response with optional operation metadata structure.

    If the request contains `include_metadata` flag, then the response should include
    `metadata` field with information about the operation performed. At the moment,
    this includes a list of fields that have been changed.
    """

    data = {"items": rows}
    if str_to_bool(str(request.GET.get("include_metadata"))):
        data["metadata"] = {
            "updated_field_ids": updated_field_ids
            if updated_field_ids is not None
            else [field.id for field in model.get_fields()]
        }
        if cascade_update:
            data["metadata"]["cascade_update"] = {
                "rows": cascade_update.updated_rows,
                "field_ids": cascade_update.field_ids,
            }
    response_serializer = serializer_class(data)
    return Response(response_serializer.data)


class RowsView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the rows of the table related to the provided "
                "value.",
            ),
            OpenApiParameter(
                name="page",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines which page of rows should be returned.",
            ),
            OpenApiParameter(
                name="size",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines how many rows should be returned per page.",
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
                "descending (Z-A). "
                "If the `user_field_names` parameter is provided then "
                "instead order_by should be a comma separated list of the actual "
                "field names. For field names with commas you should surround the "
                'name with quotes like so: `order_by=My Field,"Field With , "`. '
                "A backslash can be used to escape field names which contain "
                'double quotes like so: `order_by=My Field,Field with \\"`.',
            ),
            *ADHOC_FILTERS_API_PARAMS,
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "All the fields are included in the response by default. You can "
                    "select a subset of fields by providing the include query "
                    "parameter. If you for example provide the following GET "
                    "parameter `include=field_1,field_2` then only the fields with"
                    "id `1` and id `2` are going to be selected and included in the "
                    "response. "
                    "If the `user_field_names` parameter is provided then "
                    "instead include should be a comma separated list of the actual "
                    "field names. For field names with commas you should surround the "
                    'name with quotes like so: `include=My Field,"Field With , "`. '
                    "A backslash can be used to escape field names which contain "
                    'double quotes like so: `include=My Field,Field with \\"`.'
                ),
            ),
            OpenApiParameter(
                name="exclude",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "All the fields are included in the response by default. You can "
                    "select a subset of fields by providing the exclude query "
                    "parameter. If you for example provide the following GET "
                    "parameter `exclude=field_1,field_2` then the fields with id `1` "
                    "and id `2` are going to be excluded from the selection and "
                    "response. "
                    "If the `user_field_names` parameter is provided then "
                    "instead exclude should be a comma separated list of the actual "
                    "field names. For field names with commas you should surround the "
                    'name with quotes like so: `exclude=My Field,"Field With , "`. '
                    "A backslash can be used to escape field names which contain "
                    'double quotes like so: `exclude=My Field,Field with \\"`.'
                ),
            ),
            OpenApiParameter(
                name="{link_row_field}__join={target_field},{target_field2}",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "This parameter allows you to "
                    "request a lookup of field values from a target "
                    "table through existing link row fields. "
                    "The parameter name has to be the name of an existing link row "
                    "field, followed by `__join`. The value should be a list of "
                    "field names for which we want to lookup additional values. "
                    "You can provide one or multiple target fields. It is not possible "
                    "to lookup a value of a link row field in the target table. "
                    "If `user_field_names` parameter is set, the names of the fields "
                    "should be user field names. In this case the resulting field "
                    "names in the output will also be user field names. "
                    "The used link row field has to be among the requested fields "
                    "if using the `include` or `exclude` parameters."
                ),
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause the returned JSON to use the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Includes all the filters and sorts of the provided view.",
            ),
            SEARCH_MODE_API_PARAM,
        ],
        tags=["Database table rows"],
        operation_id="list_database_table_rows",
        description=(
            "Lists all the rows of the table related to the provided parameter if the "
            "user has access to the related database's workspace. The response is "
            "paginated by a page/size style. It is also possible to provide an "
            "optional search query, only rows where the data matches the search query "
            "are going to be returned then. The properties of the returned rows "
            "depends on which fields the table has. For a complete overview of fields "
            "use the **list_database_table_fields** endpoint to list them all. In the "
            "example all field types are listed, but normally the number in "
            "field_{id} key is going to be the id of the field. Or if the GET "
            "parameter `user_field_names` is provided then the keys will be the name "
            "of the field. The value is what the user has provided and the format of "
            "it depends on the fields type."
        ),
        responses={
            200: example_pagination_row_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_PAGE_SIZE_LIMIT",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                [
                    "ERROR_TABLE_DOES_NOT_EXIST",
                    "ERROR_FIELD_DOES_NOT_EXIST",
                    "ERROR_VIEW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            IncompatibleField: ERROR_INCOMPATIBLE_FIELD_TYPE,
            InvalidJoinParameterException: ERROR_INVALID_JOIN_PARAMETER,
        }
    )
    @validate_query_parameters(ListRowsQueryParamsSerializer)
    def get(self, request, table_id, query_params):
        """
        Lists all the rows of the given table id paginated. It is also possible to
        provide a search query.
        """

        table = TableHandler().get_table(table_id)

        CoreHandler().check_permissions(
            request.user,
            ListRowsDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        TokenHandler().check_table_permissions(request, "read", table, False)
        search = query_params.get("search")
        search_mode = query_params.get("search_mode")
        order_by = query_params.get("order_by")
        include = query_params.get("include")
        exclude = query_params.get("exclude")
        user_field_names = extract_user_field_names_from_params(request.GET)
        view_id = query_params.get("view_id")
        fields_base_queryset = Field.objects.select_related("content_type").filter(
            table=table
        )
        fields = get_include_exclude_fields(
            table,
            include,
            exclude,
            queryset=fields_base_queryset,
            user_field_names=user_field_names,
        )
        link_row_fields_queryset = (
            fields if fields is not None else fields_base_queryset
        )
        link_row_fields = link_row_fields_queryset.filter(
            content_type__model="linkrowfield"
        )
        link_row_joins = extract_link_row_joins_from_request(
            request, link_row_fields, user_field_names=user_field_names
        )
        field_kwargs = {
            f"field_{link_row_join.link_row_field_id}": {"link_row_join": link_row_join}
            for link_row_join in link_row_joins
        }

        if view_id:
            view_handler = ViewHandler()
            view = view_handler.get_view_as_user(
                request.user,
                view_id,
                base_queryset=View.objects.prefetch_related("viewsort_set"),
            )

            if view.table_id != table.id:
                raise ViewDoesNotExist()

            # Ensure fields used for filtering, sorting, or grouping are included in the
            # queryset. Unrequested fields will be filtered out later in the serializer.

            model = table.get_model()
            queryset = model.objects.all().enhance_by_fields(**field_kwargs)
            queryset = view_handler.apply_filters(view, queryset)
            queryset = view_handler.apply_sorting(view, queryset)
        else:
            model = table.get_model(
                fields=fields,
                field_ids=[] if fields else None,
            )
            queryset = model.objects.all().enhance_by_fields(**field_kwargs)

        adhoc_filters = AdHocFilters.from_request(
            request, user_field_names=user_field_names
        )
        if adhoc_filters.has_any_filters:
            queryset = adhoc_filters.apply_to_queryset(model, queryset)

        if search:
            queryset = queryset.search_all_fields(search, search_mode=search_mode)

        if order_by:
            queryset = queryset.order_by_fields_string(order_by, user_field_names)

        paginator = PageNumberPagination(limit_page_size=settings.ROW_PAGE_SIZE_LIMIT)
        page = paginator.paginate_queryset(queryset, request, self)
        serializer_class = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            field_ids=[f.id for f in fields] if fields else None,
            user_field_names=user_field_names,
            field_kwargs=field_kwargs,
        )
        serializer = serializer_class(page, many=True)

        rows_loaded.send(sender=self, table=table)

        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a row in the table related to the provided value.",
            ),
            OpenApiParameter(
                name="before",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="If provided then the newly created row will be "
                "positioned before the row with the provided id.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the row is created in a view. This can result "
                "in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause this endpoint to expect and return the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table rows"],
        operation_id="create_database_table_row",
        description=(
            "Creates a new row in the table if the user has access to the related "
            "table's workspace. The accepted body fields are depending on the fields "
            "that the table has. For a complete overview of fields use the "
            "**list_database_table_fields** to list them all. None of the fields are "
            "required, if they are not provided the value is going to be `null` or "
            "`false` or some default value is that is set. If you want to add a value "
            "for the field with for example id `10`, the key must be named `field_10`. "
            "Or instead if the `user_field_names` GET param is provided the key must "
            "be the name of the field. Of course multiple fields can be provided in "
            "one request. In the examples below you will find all the different field "
            "types, the numbers/ids in the example are just there for example "
            "purposes, the field_ID must be replaced with the actual id of the field "
            "or the name of the field if `user_field_names` is provided."
        ),
        request=get_example_row_serializer_class(
            example_type="post", user_field_names=True
        ),
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=True
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            CannotCreateRowsInTable: ERROR_CANNOT_CREATE_ROWS_IN_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(CreateRowQueryParamsSerializer)
    def post(self, request: Request, table_id: int, query_params) -> Response:
        """
        Creates a new row for the given table_id. Also the post data is validated
        according to the tables field types.
        """

        table = TableHandler().get_table(table_id)
        request_data = deepcopy(request.data)

        TokenHandler().check_table_permissions(request, "create", table, False)

        user_field_names = extract_user_field_names_from_params(request.GET)
        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        model = table.get_model()

        validation_serializer = get_row_serializer_class(
            model, user_field_names=user_field_names
        )
        data = validate_data(validation_serializer, request_data)

        before_id = query_params.get("before")
        before_row = (
            RowHandler().get_row(request.user, table, before_id, model)
            if before_id
            else None
        )

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        try:
            row = action_type_registry.get_by_type(CreateRowActionType).do(
                request.user,
                table,
                data,
                model=model,
                before_row=before_row,
                view=view,
                user_field_names=user_field_names,
                send_webhook_events=send_webhook_events,
            )
        except ValidationError as e:
            raise RequestBodyValidationException(detail=e.message)

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        serializer = serializer_class(row)

        return Response(serializer.data)


class RowNamesView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table__{id}",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A list of comma separated row ids to query from the table with "
                    "id {id}. For example, if you "
                    "want the name of row `42` and `43` from table `28` this parameter "
                    "will be `table__28=42,43`. You can specify multiple rows for "
                    "different tables but every tables must be in the same database. "
                    "You need at least read permission on all specified tables."
                ),
            ),
        ],
        tags=["Database table rows"],
        operation_id="list_database_table_row_names",
        description=(
            "Returns the names of the given row of the given tables. The name"
            "of a row is the primary field value for this row. The result can be used"
            "for example, when you want to display the name of a linked row from "
            "another table."
        ),
        responses={
            200: row_names_response_schema,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
        }
    )
    def get(self, request):
        """
        Returns the names (i.e. primary field value) of specified rows of given tables.
        Can be used when you want to display a row name referenced from another table.
        """

        result = {}
        database = None
        table_handler = TableHandler()
        token_handler = TokenHandler()
        row_handler = RowHandler()

        for name, value in request.GET.items():
            if not name.startswith("table__"):
                raise QueryParameterValidationException(
                    detail='Only table Id prefixed by "table__" are allowed as '
                    "parameter.",
                    code="invalid_parameter",
                )

            try:
                table_id = int(name[7:])
            except ValueError:
                raise QueryParameterValidationException(
                    detail=(f'Failed to parse table id in "{name}".'),
                    code="invalid_table_id",
                )

            try:
                row_ids = [int(id) for id in value.split(",")]
            except ValueError:
                raise QueryParameterValidationException(
                    detail=(
                        f'Failed to parse row ids in "{value}" for '
                        f'"table__{table_id}" parameter.'
                    ),
                    code="invalid_row_ids",
                )

            table_queryset = None
            if database:
                # Once we have the database, we want only tables from the same database
                table_queryset = Table.objects.filter(database=database)

            table = table_handler.get_table(table_id, base_queryset=table_queryset)

            if not database:
                database = table.database

            CoreHandler().check_permissions(
                request.user,
                ListRowNamesDatabaseTableOperationType.type,
                workspace=database.workspace,
                context=table,
            )

            token_handler.check_table_permissions(request, "read", table, False)

            result[table_id] = row_handler.get_row_names(table, row_ids)

        return Response(result)


class RowView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the row of the table related to the provided "
                "value.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the row related the provided value.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the row if fetched in a view. This can result "
                "in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause the returned JSON to use the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "Optionally include row's `metadata` in the response. "
                    "The `metadata` object includes extra row specific data like the "
                    "'row_comments_notification_mode' settings, if available."
                ),
            ),
        ],
        tags=["Database table rows"],
        operation_id="get_database_table_row",
        description=(
            "Fetches an existing row from the table if the user has access to the "
            "related table's workspace. The properties of the returned row depend on "
            "which fields the table has. For a complete overview of fields use the "
            "**list_database_table_fields** endpoint to list them all. In the example "
            "all field types are listed, but normally the number in field_{id} key is "
            "going to be the id of the field of the field. Or if the GET parameter "
            "`user_field_names` is provided then the keys will be the name of the "
            "field. The value is what the user has provided and the format of it "
            "depends on the fields type."
        ),
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=True
            ),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            TokenCannotIncludeRowMetadata: ERROR_CANNOT_INCLUDE_ROW_METADATA,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @allowed_includes("metadata")
    @validate_query_parameters(GetRowQueryParamsSerializer)
    def get(self, request, table_id, row_id, metadata, query_params: dict):
        """
        Responds with a serializer version of the row related to the provided row_id
        and table_id.
        """

        table = TableHandler().get_table(table_id)

        token_handler = TokenHandler()
        db_token = token_handler.get_token_from_request(request)
        if db_token is not None:
            if metadata:
                raise TokenCannotIncludeRowMetadata()
            token_handler.check_table_permissions(db_token, "read", table)

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        user_field_names = extract_user_field_names_from_params(request.GET)
        model = table.get_model()
        row = RowHandler().get_row(request.user, table, row_id, model, view=view)
        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        serializer = serializer_class(row)
        response_data = serializer.data

        if metadata:
            row_metadata = serialize_single_row_metadata(request.user, row)
            response_data["metadata"] = row_metadata

        rows_loaded.send(sender=self, table=table)

        return Response(response_data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the row in the table related to the value.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the row related to the value.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the row is updated in a view. This can result "
                "in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause this endpoint to expect and return the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table rows"],
        operation_id="update_database_table_row",
        description=(
            "Updates an existing row in the table if the user has access to the "
            "related table's workspace. The accepted body fields are depending on the "
            "fields that the table has. For a complete overview of fields use the "
            "**list_database_table_fields** endpoint to list them all. None of the "
            "fields are required, if they are not provided the value is not going to "
            "be updated. "
            "When you want to update a value for the field with id `10`, the key must "
            "be named `field_10`. Or if the GET parameter `user_field_names` is "
            "provided the key of the field to update must be the name of the field. "
            "Multiple different fields to update can be provided in one request. In "
            "the examples below you will find all the different field types, the "
            "numbers/ids in the example are just there for example purposes, "
            "the field_ID must be replaced with the actual id of the field or the name "
            "of the field if `user_field_names` is provided."
        ),
        request=get_example_row_serializer_class(
            example_type="patch", user_field_names=True
        ),
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=True
            ),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @require_request_data_type(dict)
    @validate_query_parameters(UpdateRowQueryParamsSerializer)
    def patch(
        self, request: Request, table_id: int, row_id: int, query_params
    ) -> Response:
        """
        Updates the row with the given row_id for the table with the given
        table_id. Also the post data is validated according to the tables field types.

        :param request: The request object
        :param table_id: The id of the table to update the row in
        :param row_id: The id of the row to update
        :return: The updated row values serialized as a json object
        """

        table = TableHandler().get_table(table_id)
        TokenHandler().check_table_permissions(request, "update", table, False)

        request_data = deepcopy(request.data)

        user_field_names = extract_user_field_names_from_params(request.GET)
        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        field_ids, field_names = None, None

        if user_field_names:
            field_names = request_data.keys()
        else:
            field_ids = RowHandler().extract_field_ids_from_dict(request_data)

        model = table.get_model()
        validation_serializer = get_row_serializer_class(
            model,
            field_ids=field_ids,
            field_names_to_include=field_names,
            user_field_names=user_field_names,
        )
        data = validate_data(validation_serializer, request_data, return_validated=True)
        try:
            data["id"] = int(row_id)
            row = (
                action_type_registry.get_by_type(UpdateRowsActionType)
                .do(
                    request.user,
                    table,
                    [data],
                    model=model,
                    view=view,
                    send_webhook_events=send_webhook_events,
                )
                .updated_rows[0]
            )
        except ValidationError as exc:
            raise RequestBodyValidationException(detail=exc.message) from exc

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        serializer = serializer_class(row)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the row in the table related to the value.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the row is deleted in a view. This can result "
                "in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the row related to the value.",
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table rows"],
        operation_id="delete_database_table_row",
        description=(
            "Deletes an existing row in the table if the user has access to the "
            "table's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM"]
            ),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
            CannotDeleteRowsInTable: ERROR_CANNOT_DELETE_ROWS_IN_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(DeleteRowQueryParamsSerializer)
    def delete(self, request, table_id, row_id, query_params):
        """
        Deletes an existing row with the given row_id for table with the given
        table_id.
        """

        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        table = TableHandler().get_table(table_id)
        TokenHandler().check_table_permissions(request, "delete", table, False)

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        action_type_registry.get_by_type(DeleteRowActionType).do(
            request.user,
            table,
            row_id,
            view=view,
            send_webhook_events=send_webhook_events,
        )

        return Response(status=204)


class RowMoveView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Moves the row in the table related to the value.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Moves the row related to the value.",
            ),
            OpenApiParameter(
                name="before_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Moves the row related to the given `row_id` before the "
                "row related to the provided value. If not provided, "
                "then the row will be moved to the end.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause the returned JSON to use the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table rows"],
        operation_id="move_database_table_row",
        description="Moves the row related to given `row_id` parameter to another "
        "position. It is only possible to move the row before another existing row or "
        "to the end. If the `before_id` is provided then the row related to "
        "the `row_id` parameter is moved before that row. If the `before_id` "
        "parameter is not provided, then the row will be moved to the end.",
        request=None,
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=True
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(MoveRowQueryParamsSerializer)
    def patch(self, request, table_id, row_id, query_params):
        """Moves the row to another position."""

        table = TableHandler().get_table(table_id)

        TokenHandler().check_table_permissions(request, "update", table, False)

        user_field_names = extract_user_field_names_from_params(request.GET)
        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        model = table.get_model()

        row_handler = RowHandler()

        before_id = query_params.get("before_id")
        before_row = (
            row_handler.get_row(request.user, table, before_id, model=model)
            if before_id
            else None
        )

        row = action_type_registry.get_by_type(MoveRowActionType).do(
            request.user,
            table,
            row_id,
            before_row=before_row,
            model=model,
            send_webhook_events=send_webhook_events,
        )

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        serializer = serializer_class(row)
        return Response(serializer.data)


class BatchRowsView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates the rows in the table.",
            ),
            OpenApiParameter(
                name="before",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="If provided then the newly created rows will be "
                "positioned before the row with the provided id.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the rows are created in a view. This can result "
                "in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause this endpoint to expect and return the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
            INCLUDE_OPERATION_METADATA,
        ],
        tags=["Database table rows"],
        operation_id="batch_create_database_table_rows",
        description=(
            "Creates new rows in the table if the user has access to the related "
            "table's workspace. The accepted body fields are depending on the fields "
            "that the table has. For a complete overview of fields use the "
            "**list_database_table_fields** to list them all. None of the fields are "
            "required, if they are not provided the value is going to be `null` or "
            "`false` or some default value is that is set. If you want to add a value "
            "for the field with for example id `10`, the key must be named `field_10`. "
            "Or instead if the `user_field_names` GET param is provided the key must "
            "be the name of the field. Of course multiple fields can be provided in "
            "one request. In the examples below you will find all the different field "
            "types, the numbers/ids in the example are just there for example "
            "purposes, the field_ID must be replaced with the actual id of the field "
            "or the name of the field if `user_field_names` is provided."
            "\n\n **WARNING:** This endpoint doesn't yet work with row created webhooks."
        ),
        request=get_example_batch_rows_serializer_class(
            example_type="post", user_field_names=True, request_serializer=True
        ),
        responses={
            200: get_example_batch_rows_serializer_class(
                example_type="post", user_field_names=True, request_serializer=False
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ROW_IDS_NOT_UNIQUE",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            RowIdsNotUnique: ERROR_ROW_IDS_NOT_UNIQUE,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            CannotCreateRowsInTable: ERROR_CANNOT_CREATE_ROWS_IN_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(BatchCreateRowsQueryParamsSerializer)
    def post(self, request: Request, table_id: int, query_params) -> Response:
        """
        Creates new rows for the given table_id. Also the post data is validated
        according to the tables field types.
        """

        table = TableHandler().get_table(table_id)
        TokenHandler().check_table_permissions(request, "create", table, False)
        model = table.get_model()
        request_data = deepcopy(request.data)

        user_field_names = extract_user_field_names_from_params(request.GET)
        send_webhook_events = extract_send_webhook_events_from_params(request.GET)
        before_id = query_params.get("before")
        before_row = (
            RowHandler().get_row(request.user, table, before_id, model)
            if before_id
            else None
        )

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        row_validation_serializer = get_row_serializer_class(
            model, user_field_names=user_field_names
        )
        validation_serializer = get_batch_row_serializer_class(
            row_validation_serializer
        )
        data = validate_data(
            validation_serializer, request_data, partial=True, return_validated=True
        )

        try:
            rows = action_type_registry.get_by_type(CreateRowsActionType).do(
                request.user,
                table,
                data["items"],
                before_row,
                view=view,
                model=model,
                send_webhook_events=send_webhook_events,
            )
        except ValidationError as exc:
            raise RequestBodyValidationException(detail=exc.message)

        response_row_serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        response_serializer_class = get_batch_row_serializer_class(
            response_row_serializer_class
        )

        return build_response_with_metadata(
            rows=rows,
            request=request,
            model=model,
            serializer_class=response_serializer_class,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the rows in the table.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the rows are updated in a view. This can "
                "result in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause this endpoint to expect and return the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
            INCLUDE_OPERATION_METADATA,
        ],
        tags=["Database table rows"],
        operation_id="batch_update_database_table_rows",
        description=(
            "Updates existing rows in the table if the user has access to the "
            "related table's workspace. The accepted body fields are depending on the "
            "fields that the table has. For a complete overview of fields use the "
            "**list_database_table_fields** endpoint to list them all. None of the "
            "fields are required, if they are not provided the value is not going to "
            "be updated. "
            "When you want to update a value for the field with id `10`, the key must "
            "be named `field_10`. Or if the GET parameter `user_field_names` is "
            "provided the key of the field to update must be the name of the field. "
            "Multiple different fields to update can be provided for each row. In "
            "the examples below you will find all the different field types, the "
            "numbers/ids in the example are just there for example purposes, "
            "the field_ID must be replaced with the actual id of the field or the name "
            "of the field if `user_field_names` is provided."
            "\n\n **WARNING:** This endpoint doesn't yet work with row updated webhooks."
        ),
        request=get_example_batch_rows_serializer_class(
            example_type="patch_batch", user_field_names=True, request_serializer=True
        ),
        responses={
            200: get_example_batch_rows_serializer_class(
                example_type="patch_batch",
                user_field_names=True,
                request_serializer=False,
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ROW_IDS_NOT_UNIQUE",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            RowIdsNotUnique: ERROR_ROW_IDS_NOT_UNIQUE,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(BatchUpdateRowsQueryParamsSerializer)
    def patch(self, request, table_id, query_params):
        """
        Updates all provided rows at once for the table with
        the given table_id.
        """

        table = TableHandler().get_table(table_id)
        TokenHandler().check_table_permissions(request, "update", table, False)
        model = table.get_model()
        request_data = deepcopy(request.data)

        user_field_names = extract_user_field_names_from_params(request.GET)
        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        row_validation_serializer = get_row_serializer_class(
            model,
            user_field_names=user_field_names,
            include_id=True,
            required_fields=["id"],
        )
        validation_serializer = get_batch_row_serializer_class(
            row_validation_serializer
        )
        data = validate_data(
            validation_serializer, request_data, partial=True, return_validated=True
        )

        try:
            updated_data = action_type_registry.get_by_type(UpdateRowsActionType).do(
                request.user,
                table,
                data["items"],
                model=model,
                view=view,
                send_webhook_events=send_webhook_events,
            )
            rows = updated_data.updated_rows
        except ValidationError as e:
            raise RequestBodyValidationException(detail=e.message)

        response_row_serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        response_serializer_class = get_batch_row_serializer_class(
            response_row_serializer_class
        )
        return build_response_with_metadata(
            rows=rows,
            request=request,
            model=model,
            serializer_class=response_serializer_class,
            updated_field_ids=updated_data.updated_field_ids,
            cascade_update=updated_data.cascade_update,
        )


class BatchDeleteRowsView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the rows in the table related to the value.",
            ),
            OpenApiParameter(
                name="view",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Provide if the rows are deleted in a view. This can "
                "result in different permission checking and default values.",
            ),
            OpenApiParameter(
                name="send_webhook_events",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that triggers webhooks after the operation,"
                    " if set to `y`, `yes`, `true`, `t`, `on`, `1`, or left empty. "
                    "Defaults to `true`"
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table rows"],
        operation_id="batch_delete_database_table_rows",
        description=(
            "Deletes existing rows in the table if the user has access to the "
            "table's workspace."
            "\n\n **WARNING:**  This endpoint doesn't yet work with row deleted webhooks."
        ),
        request=BatchDeleteRowsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM",
                    "ERROR_ROW_IDS_NOT_UNIQUE",
                ]
            ),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @validate_body(BatchDeleteRowsSerializer)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            RowIdsNotUnique: ERROR_ROW_IDS_NOT_UNIQUE,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
            CannotDeleteRowsInTable: ERROR_CANNOT_DELETE_ROWS_IN_TABLE,
            DeadlockException: ERROR_DATABASE_DEADLOCK,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @atomic_with_retry_on_deadlock()
    @validate_query_parameters(BatchDeleteRowsQueryParamsSerializer)
    def post(
        self, request: Request, table_id: int, data: Dict[str, Any], query_params
    ) -> Response:
        """
        Batch deletes existing rows based on provided row ids for the table with
        the given table_id.
        """

        table = TableHandler().get_table(table_id)
        TokenHandler().check_table_permissions(request, "delete", table, False)

        send_webhook_events = extract_send_webhook_events_from_params(request.GET)

        view_id = query_params.get("view")
        view = ViewHandler().get_view(view_id) if view_id else None

        action_type_registry.get_by_type(DeleteRowsActionType).do(
            request.user,
            table,
            row_ids=data["items"],
            view=view,
            send_webhook_events=send_webhook_events,
        )

        return Response(status=204)


class RowAdjacentView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the row of the table related to the provided "
                "value.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the row adjacent the provided value.",
            ),
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Applies the filters and sorts of the provided view.",
            ),
            OpenApiParameter(
                name="user_field_names",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter that, if provided with one of the "
                    "following values: `y`, `yes`, `true`, `t`, `on`, `1`, or an "
                    "empty value, will cause the returned JSON to use the "
                    "user-specified field names instead of the internal Baserow "
                    "field names (e.g., field_123)."
                ),
            ),
            OpenApiParameter(
                name="previous",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description=(
                    "A flag query parameter which if provided returns the"
                    "previous row to the specified row_id. If it's not set"
                    "it will return the next row."
                ),
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided, the adjacent row will be one that matches"
                "the search query.",
            ),
            SEARCH_MODE_API_PARAM,
        ],
        tags=["Database table rows"],
        operation_id="get_adjacent_database_table_row",
        description=(
            "Fetches the adjacent row to a given row_id in the table with the "
            "given table_id. If the previous flag is set it will return the "
            "previous row, otherwise it will return the next row. You can specify"
            "a view_id and it will apply the filters and sorts of the provided "
            "view."
        ),
        responses={
            200: get_example_row_serializer_class(
                example_type="get", user_field_names=True
            ),
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(
                [
                    "ERROR_TABLE_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                    "ERROR_VIEW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(GetRowAdjacentSerializer)
    def get(
        self, request: Request, table_id: int, row_id: int, query_params: Dict[str, Any]
    ) -> Response:
        previous = query_params.get("previous")
        view_id = query_params.get("view_id")
        user_field_names = query_params.get("user_field_names")
        search = query_params.get("search")
        search_mode = query_params.get("search_mode")

        table = TableHandler().get_table(table_id)
        CoreHandler().check_permissions(
            request.user,
            ReadAdjacentRowDatabaseRowOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        model = table.get_model()

        if view_id is None:
            view = None
        else:
            view = ViewHandler().get_view_as_user(
                request.user, view_id, table_id=table.id
            )

        adjacent_row = RowHandler().get_adjacent_row(
            model,
            row_id,
            previous=previous,
            view=view,
            search=search,
            search_mode=search_mode,
        )

        # Don't fail, just let the user know there isn't an adjacent row
        if adjacent_row is None:
            return Response(status=HTTP_204_NO_CONTENT)

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, user_field_names=user_field_names
        )
        serializer = serializer_class(adjacent_row)

        return Response(serializer.data)


class RowHistoryView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the table to fetch the row change history from.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the row to fetch the change history from.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The maximum number of row change history entries to return.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The offset of the row change history entries to return.",
            ),
        ],
        tags=["Database table rows"],
        operation_id="get_database_table_row_history",
        description=(
            "Fetches the row change history of a given row_id in the table with the "
            "given table_id. The row change history is paginated and can be limited "
            "with the limit and offset query parameters."
        ),
        responses={
            200: get_example_pagination_serializer_class(RowHistorySerializer),
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_TABLE_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, table_id: int, row_id: int) -> Response:
        paginator = LimitOffsetPagination()
        paginator.max_limit = settings.ROW_PAGE_SIZE_LIMIT
        paginator.default_limit = settings.ROW_PAGE_SIZE_LIMIT

        table = TableHandler().get_table(table_id)
        CoreHandler().check_permissions(
            request.user,
            ReadDatabaseRowHistoryOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        table_model = table.get_model()

        try:
            table_model.objects.only("id").get(pk=row_id)
        except table_model.DoesNotExist:
            raise RowDoesNotExist(row_id)

        row_history = RowHistoryHandler.list_row_history(
            table.database.workspace, table_id, row_id
        )
        page = paginator.paginate_queryset(row_history, request, self)

        return paginator.get_paginated_response(
            RowHistorySerializer(page, many=True).data
        )
