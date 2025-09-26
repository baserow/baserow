from collections import defaultdict
from typing import Any, Dict

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import ObjectDoesNotExist

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    allowed_includes,
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.search.serializers import SearchQueryParamSerializer
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    MappingSerializer,
    validate_data,
    validate_data_custom_fields,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FIELD_NOT_IN_TABLE,
)
from baserow.contrib.database.api.fields.serializers import LinkRowValueSerializer
from baserow.contrib.database.api.rows.errors import ERROR_ROW_DOES_NOT_EXIST
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_example_row_serializer_class,
    get_row_serializer_class,
)
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.api.views.serializers import (
    CreateViewGroupBySerializer,
    PublicViewInfoSerializer,
    UpdateViewGroupBySerializer,
    ViewGroupBySerializer,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    FieldNotInTable,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.actions import (
    CreateDecorationActionType,
    CreateViewActionType,
    CreateViewFilterActionType,
    CreateViewFilterGroupActionType,
    CreateViewGroupByActionType,
    CreateViewSortActionType,
    DeleteDecorationActionType,
    DeleteViewActionType,
    DeleteViewFilterActionType,
    DeleteViewFilterGroupActionType,
    DeleteViewGroupByActionType,
    DeleteViewSortActionType,
    DuplicateViewActionType,
    OrderViewsActionType,
    RotateViewSlugActionType,
    UpdateDecorationActionType,
    UpdateViewActionType,
    UpdateViewFieldOptionsActionType,
    UpdateViewFilterActionType,
    UpdateViewFilterGroupActionType,
    UpdateViewGroupByActionType,
    UpdateViewSortActionType,
)
from baserow.contrib.database.views.exceptions import (
    CannotShareViewTypeError,
    DecoratorValueProviderTypeNotCompatible,
    NoAuthorizationToPubliclySharedView,
    UnrelatedFieldError,
    ViewDecorationDoesNotExist,
    ViewDecorationNotSupported,
    ViewDoesNotExist,
    ViewDoesNotSupportFieldOptions,
    ViewDoesNotSupportListingRows,
    ViewFilterDoesNotExist,
    ViewFilterGroupDoesNotExist,
    ViewFilterNotSupported,
    ViewFilterTypeNotAllowedForField,
    ViewGroupByDoesNotExist,
    ViewGroupByFieldAlreadyExist,
    ViewGroupByFieldNotSupported,
    ViewGroupByNotSupported,
    ViewNotInTable,
    ViewOwnershipTypeDoesNotExist,
    ViewSortDoesNotExist,
    ViewSortFieldAlreadyExist,
    ViewSortFieldNotSupported,
    ViewSortNotSupported,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.operations import (
    DeleteViewDecorationOperationType,
    ListViewsOperationType,
)
from baserow.contrib.database.views.registries import (
    decorator_value_provider_type_registry,
    view_type_registry,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.db import specific_iterator
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from ..constants import SEARCH_MODE_API_PARAM
from .errors import (
    ERROR_CANNOT_SHARE_VIEW_TYPE,
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_UNRELATED_FIELD,
    ERROR_VIEW_DECORATION_DOES_NOT_EXIST,
    ERROR_VIEW_DECORATION_NOT_SUPPORTED,
    ERROR_VIEW_DECORATION_VALUE_PROVIDER_NOT_COMPATIBLE,
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS,
    ERROR_VIEW_DOES_NOT_SUPPORT_LISTING_ROWS,
    ERROR_VIEW_FILTER_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_NOT_SUPPORTED,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
    ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST,
    ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS,
    ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED,
    ERROR_VIEW_GROUP_BY_NOT_SUPPORTED,
    ERROR_VIEW_NOT_IN_TABLE,
    ERROR_VIEW_OWNERSHIP_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_SORT_DOES_NOT_EXIST,
    ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS,
    ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED,
    ERROR_VIEW_SORT_NOT_SUPPORTED,
)
from .serializers import (
    CreateViewDecorationSerializer,
    CreateViewFilterGroupSerializer,
    CreateViewFilterSerializer,
    CreateViewSerializer,
    CreateViewSortSerializer,
    ListQueryParamatersSerializer,
    OrderViewsSerializer,
    PublicViewAuthRequestSerializer,
    PublicViewAuthResponseSerializer,
    UpdateViewDecorationSerializer,
    UpdateViewFilterGroupSerializer,
    UpdateViewFilterSerializer,
    UpdateViewSerializer,
    UpdateViewSortSerializer,
    ViewDecorationSerializer,
    ViewFilterGroupSerializer,
    ViewFilterSerializer,
    ViewSerializer,
    ViewSortSerializer,
)
from .utils import get_public_view_authorization_token

view_field_options_mapping_serializer = MappingSerializer(
    "ViewFieldOptions",
    view_type_registry.get_field_options_serializer_map(),
    "view_type",
)


def get_decoration_mapping_serializer(base_serializer, many=False):
    return DiscriminatorCustomFieldsMappingSerializer(
        decorator_value_provider_type_registry,
        base_serializer,
        type_field_name="value_provider_type",
        many=many,
    )


class ViewsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only views of the table related to the provided "
                "value.",
            ),
            OpenApiParameter(
                name="type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "Optionally filter on the view type. If provided, only views of "
                    "that type will be returned."
                ),
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description=(
                    "The maximum amount of views that must be returned. This endpoint "
                    "doesn't support pagination, but if you for example just need to "
                    "fetch the first view, you can do that by setting a limit. There "
                    "isn't a limit by default."
                ),
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list of extra attributes to include on each "
                    "view in the response. The supported attributes are `filters`, "
                    "`sortings` and `decorations`. "
                    "For example `include=filters,sortings` will add the "
                    "attributes `filters` and `sortings` to every returned view, "
                    "containing a list of the views filters and sortings respectively."
                ),
            ),
        ],
        tags=["Database table views"],
        operation_id="list_database_table_views",
        description=(
            "Lists all views of the table related to the provided `table_id`. If the workspace"
            " is related to a template, then this endpoint will be publicly accessible. A "
            "table can have multiple views. Each view can display the data in a "
            "different way. For example the `grid` view shows the in a spreadsheet "
            "like way. That type has custom endpoints for data retrieval and "
            "manipulation. In the future other views types like a calendar or Kanban "
            "are going to be added. Each type can have different properties."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry, ViewSerializer, many=True
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_query_parameters(ListQueryParamatersSerializer)
    @allowed_includes("filters", "sortings", "decorations", "group_bys")
    def get(
        self, request, table_id, query_params, filters, sortings, decorations, group_bys
    ):
        """
        Responds with a list of serialized views that belong to the table if the user
        has access to that workspace.
        """

        table = TableHandler().get_table(table_id)
        CoreHandler().check_permissions(
            request.user,
            ListViewsOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        views = ViewHandler().list_views(
            request.user,
            table,
            query_params["type"],
            filters,
            sortings,
            decorations,
            group_bys,
            query_params["limit"],
        )

        views_by_type = defaultdict(list)
        for view in views:
            views_by_type[type(view)].append(view)

        serialized_views = []
        for _, views in views_by_type.items():
            serialized_views += view_type_registry.get_serializer(
                views,
                ViewSerializer,
                context={"user": request.user},
                filters=filters,
                sortings=sortings,
                decorations=decorations,
                group_bys=group_bys,
                many=True,
            ).data
        return Response(serialized_views)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a view for the table related to the provided "
                "value.",
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list of extra attributes to include on each "
                    "view in the response. The supported attributes are `filters`, "
                    "`sortings` and `decorations`. "
                    "For example `include=filters,sortings` will add the attributes "
                    "`filters` and `sortings` to every returned view, containing "
                    "a list of the views filters and sortings respectively."
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="create_database_table_view",
        description=(
            "Creates a new view for the table related to the provided `table_id` "
            "parameter. Depending on the type, different properties can optionally be "
            "set."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            view_type_registry, CreateViewSerializer
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry, ViewSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_FIELD_NOT_IN_TABLE",
                ]
            ),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body_custom_fields(
        view_type_registry,
        base_serializer_class=CreateViewSerializer,
        partial=True,
        return_validated=True,
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewOwnershipTypeDoesNotExist: ERROR_VIEW_OWNERSHIP_TYPE_DOES_NOT_EXIST,
        }
    )
    @allowed_includes("filters", "sortings", "decorations", "group_bys")
    def post(
        self,
        request: Request,
        data,
        table_id: int,
        filters,
        sortings,
        decorations,
        group_bys,
    ):
        """Creates a new view for a user."""

        type_name = data.pop("type")
        view_type = view_type_registry.get(type_name)
        table = TableHandler().get_table(table_id)

        with view_type.map_api_exceptions():
            view = action_type_registry.get_by_type(CreateViewActionType).do(
                request.user, table, type_name, **data
            )

        serializer = view_type_registry.get_serializer(
            view,
            ViewSerializer,
            context={"user": request.user},
            filters=filters,
            sortings=sortings,
            decorations=decorations,
            group_bys=group_bys,
        )
        return Response(serializer.data)


class ViewView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the view related to the provided value.",
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list of extra attributes to include on the "
                    "returned view. The supported attributes are `filters`, "
                    "`sortings` and `decorations`. "
                    "For example `include=filters,sortings` will add the attributes "
                    "`filters` and `sortings` to every returned view, containing "
                    "a list of the views filters and sortings respectively."
                ),
            ),
        ],
        tags=["Database table views"],
        operation_id="get_database_table_view",
        description=(
            "Returns the existing view. Depending on the type different properties "
            "could be returned."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry, ViewSerializer
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @allowed_includes("filters", "sortings", "decorations", "group_bys")
    def get(self, request, view_id, filters, sortings, decorations, group_bys):
        """Selects a single view and responds with a serialized version."""

        view = ViewHandler().get_view_as_user(request.user, view_id)

        serializer = view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=filters,
            sortings=sortings,
            decorations=decorations,
            group_bys=group_bys,
            context={"user": request.user},
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the view related to the provided value.",
            ),
            OpenApiParameter(
                name="include",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "A comma separated list of extra attributes to include on the "
                    "returned view. The supported attributes are `filters`, "
                    "`sortings` and `decorations`. "
                    "For example `include=filters,sortings` will add the attributes "
                    "`filters` and `sortings` to every returned view, containing "
                    "a list of the views filters and sortings respectively."
                ),
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="update_database_table_view",
        description=(
            "Updates the existing view. The type cannot be changed. It depends "
            "on the existing type which properties can be changed."
        ),
        request=CustomFieldRegistryMappingSerializer(
            view_type_registry, UpdateViewSerializer
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry, ViewSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_FIELD_NOT_IN_TABLE",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @allowed_includes("filters", "sortings", "decorations", "group_bys")
    def patch(
        self,
        request: Request,
        view_id: int,
        filters: bool,
        sortings: bool,
        decorations: bool,
        group_bys: bool,
    ) -> Response:
        """Updates the view."""

        view = ViewHandler().get_view_for_update(request.user, view_id).specific
        view_type = view_type_registry.get_by_model(view)
        data = validate_data_custom_fields(
            view_type.type,
            view_type_registry,
            request.data,
            base_serializer_class=UpdateViewSerializer,
            partial=True,
            return_validated=True,
        )

        with view_type.map_api_exceptions():
            view = action_type_registry.get_by_type(UpdateViewActionType).do(
                request.user, view, **data
            )

        serializer = view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=filters,
            sortings=sortings,
            decorations=decorations,
            group_bys=group_bys,
            context={"user": request.user},
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the view related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="delete_database_table_view",
        description=(
            "Deletes the existing view. Note that all the related settings of the "
            "view are going to be deleted also. The data stays intact after deleting "
            "the view because this is related to the table and not the view."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request: Request, view_id: int):
        """Deletes an existing view."""

        view = ViewHandler().get_view(view_id)

        action_type_registry.get_by_type(DeleteViewActionType).do(request.user, view)

        return Response(status=204)


class DuplicateViewView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Duplicates the view related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="duplicate_database_table_view",
        description=(
            "Duplicates an existing view if the user has access to it. "
            "When a view is duplicated everything is copied except:"
            "\n- The name is appended with the copy number. "
            "Ex: `ViewName`->`ViewName(2)` and `View(2)`->`View(3)`"
            "\n- If the original view is publicly shared, the new view will not be"
            " shared anymore"
        ),
        request=None,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry, ViewSerializer
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request, view_id):
        """Duplicates a view."""

        view = ViewHandler().get_view(view_id).specific

        view_type = view_type_registry.get_by_model(view)

        with view_type.map_api_exceptions():
            duplicate_view = action_type_registry.get_by_type(
                DuplicateViewActionType
            ).do(user=request.user, original_view=view)

        serializer = view_type_registry.get_serializer(
            duplicate_view,
            ViewSerializer,
            filters=True,
            sortings=True,
            decorations=True,
            group_bys=True,
            context={"user": request.user},
        )
        return Response(serializer.data)


class OrderViewsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the order of the views in the table related to "
                "the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="order_database_table_views",
        description=(
            "Changes the order of the provided view ids to the matching position that "
            "the id has in the list. The order of the not provided views will be "
            "set to `0`."
        ),
        request=OrderViewsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_VIEW_NOT_IN_TABLE"]
            ),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(OrderViewsSerializer)
    @transaction.atomic
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewNotInTable: ERROR_VIEW_NOT_IN_TABLE,
        }
    )
    def post(self, request, data, table_id):
        """Updates to order of the views in a table."""

        table = TableHandler().get_table(table_id)
        action_type_registry.get_by_type(OrderViewsActionType).do(
            request.user, table, data["view_ids"]
        )
        return Response(status=204)


class ViewFiltersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only filters of the view related to the provided "
                "value.",
            )
        ],
        tags=["Database table view filters"],
        operation_id="list_database_table_view_filters",
        description=(
            "Lists all filters of the view related to the provided `view_id`. A view can "
            "have multiple filters. When all the rows are requested for the view only those "
            "that apply to the filters are returned."
        ),
        responses={
            200: ViewFilterSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_id):
        """
        Responds with a list of serialized filters that belong to the view if the user
        has access to that workspace.
        """

        filters = ViewHandler().list_filters(request.user, view_id)
        serializer = ViewFilterSerializer(filters, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a filter for the view related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="create_database_table_view_filter",
        description=(
            "Creates a new filter for the view related to the provided `view_id` "
            "parameter. When the rows of a view are requested, for example via the "
            "`list_database_table_grid_view_rows` endpoint, then only the rows that "
            "apply to all the filters are going to be returned. A filter compares the "
            "value of a field to the value of a filter. It depends on the type how "
            "values are going to be compared."
        ),
        request=CreateViewFilterSerializer(),
        responses={
            200: ViewFilterSerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_FILTER_NOT_SUPPORTED",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                ]
            ),
            404: get_error_schema(
                ["ERROR_VIEW_DOES_NOT_EXIST", "ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @validate_body(CreateViewFilterSerializer)
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewFilterNotSupported: ERROR_VIEW_FILTER_NOT_SUPPORTED,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            ViewFilterGroupDoesNotExist: ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST,
        }
    )
    def post(self, request, data, view_id):
        """Creates a new filter for the provided view."""

        view = ViewHandler().get_view(view_id)
        field = FieldHandler().get_field(data["field"])

        view_filter = action_type_registry.get_by_type(CreateViewFilterActionType).do(
            request.user,
            view,
            field,
            data["type"],
            data["value"],
            data.get("group", None),
        )

        serializer = ViewFilterSerializer(view_filter)
        return Response(serializer.data)


class ViewFilterView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter to return.",
            )
        ],
        tags=["Database table view filters"],
        operation_id="get_database_table_view_filter",
        description=("Returns the existing view filter."),
        responses={
            200: ViewFilterSerializer(),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_FILTER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewFilterDoesNotExist: ERROR_VIEW_FILTER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_filter_id):
        """Selects a single filter and responds with a serialized version."""

        view_filter = ViewHandler().get_filter(request.user, view_filter_id)
        serializer = ViewFilterSerializer(view_filter)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter to update.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="update_database_table_view_filter",
        description=("Updates the existing filter."),
        request=UpdateViewFilterSerializer(),
        responses={
            200: ViewFilterSerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_FILTER_NOT_SUPPORTED",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_FILTER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateViewFilterSerializer)
    @map_exceptions(
        {
            ViewFilterDoesNotExist: ERROR_VIEW_FILTER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
        }
    )
    def patch(self, request, data, view_filter_id):
        """Updates the view filter."""

        handler = ViewHandler()
        view_filter = handler.get_filter(
            request.user,
            view_filter_id,
            base_queryset=ViewFilter.objects.select_for_update(of=("self",)),
        )

        if "field" in data:
            # We can safely assume the field exists because the
            # UpdateViewFilterSerializer has already checked that.
            data["field"] = Field.objects.get(pk=data["field"])

        if "type" in data:
            data["type_name"] = data.pop("type")

        view_filter = action_type_registry.get_by_type(UpdateViewFilterActionType).do(
            request.user,
            view_filter,
            data.get("field"),
            data.get("type_name"),
            data.get("value"),
        )

        serializer = ViewFilterSerializer(view_filter)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter to delete.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="delete_database_table_view_filter",
        description=(
            "Deletes the existing filter if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_FILTER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewFilterDoesNotExist: ERROR_VIEW_FILTER_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, view_filter_id):
        """Deletes an existing filter."""

        view_filter = ViewHandler().get_filter(request.user, view_filter_id)

        action_type_registry.get_by_type(DeleteViewFilterActionType).do(
            request.user, view_filter
        )

        return Response(status=204)


class ViewFilterGroupsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view where create the new filter group.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="create_database_table_view_filter_group",
        description=(
            "Creates a new filter group for the view related to the provided `view_id` "
            "parameter."
        ),
        request=CreateViewFilterGroupSerializer(),
        responses={
            200: ViewFilterGroupSerializer(),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(CreateViewFilterGroupSerializer)
    def post(self, request, data, view_id):
        """Creates a new filter group for the provided view."""

        view = ViewHandler().get_view(view_id)

        view_filter_group = action_type_registry.get_by_type(
            CreateViewFilterGroupActionType
        ).do(request.user, view, **data)

        serializer = ViewFilterGroupSerializer(view_filter_group)
        return Response(serializer.data)


class ViewFilterGroupView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_group_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter group to return.",
            )
        ],
        tags=["Database table view filters"],
        operation_id="get_database_table_view_filter_group",
        description=(
            "Returns the existing view filter group with the given `view_filter_group_id`."
        ),
        responses={
            200: ViewFilterGroupSerializer(),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewFilterGroupDoesNotExist: ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_filter_group_id):
        """Selects a single filter group and responds with a serialized version."""

        filter_group = ViewHandler().get_filter_group(
            request.user, view_filter_group_id
        )
        serializer = ViewFilterGroupSerializer(filter_group)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_group_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter group to update.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="update_database_table_view_filter_group",
        description=(
            "Updates the existing filter group with the given `view_filter_group_id`."
        ),
        request=UpdateViewFilterGroupSerializer(),
        responses={
            200: ViewFilterGroupSerializer(),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateViewFilterGroupSerializer)
    @map_exceptions(
        {
            ViewFilterGroupDoesNotExist: ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def patch(self, request, data, view_filter_group_id):
        """Updates the view filter group."""

        handler = ViewHandler()
        view_filter_group = handler.get_filter_group(
            request.user,
            view_filter_group_id,
            base_queryset=ViewFilterGroup.objects.select_for_update(of=("self",)),
        )

        view_filter_group = action_type_registry.get_by_type(
            UpdateViewFilterGroupActionType
        ).do(request.user, view_filter_group, **data)

        serializer = ViewFilterGroupSerializer(view_filter_group)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_filter_group_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the view filter group to delete.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view filters"],
        operation_id="delete_database_table_view_filter_group",
        description=(
            "Deletes the existing filter group with the given `view_filter_group_id`."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewFilterGroupDoesNotExist: ERROR_VIEW_FILTER_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, view_filter_group_id):
        """Deletes an existing filter group."""

        view_filter_group = ViewHandler().get_filter_group(
            request.user, view_filter_group_id
        )

        action_type_registry.get_by_type(DeleteViewFilterGroupActionType).do(
            request.user, view_filter_group
        )

        return Response(status=204)


class ViewDecorationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description=(
                    "Returns only decoration of the view given to the provided "
                    "value."
                ),
            )
        ],
        tags=["Database table view decorations"],
        operation_id="list_database_table_view_decorations",
        description=(
            "Lists all decorations of the view related to the provided `view_id` if "
            "the user has access to the related database's workspace. A view can have "
            "multiple decorations. View decorators can be used to decorate rows. This "
            "can, for example, be used to change the border or background color of "
            "a row if it matches certain conditions."
        ),
        responses={
            200: get_decoration_mapping_serializer(ViewDecorationSerializer, many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_id):
        """
        Responds with a list of serialized decorations that belong to the view.
        """

        decorations = ViewHandler().list_decorations(request.user, view_id)
        serializer = ViewDecorationSerializer(decorations, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a decoration for the view related to the given "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view decorations"],
        operation_id="create_database_table_view_decoration",
        description=(
            "Creates a new decoration for the view related to the provided `view_id` "
            "parameter if the authorized user has access to the related database's "
            "workspace."
        ),
        request=get_decoration_mapping_serializer(CreateViewDecorationSerializer),
        responses={
            200: get_decoration_mapping_serializer(ViewDecorationSerializer),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body_custom_fields(
        decorator_value_provider_type_registry,
        type_attribute_name="value_provider_type",
        base_serializer_class=CreateViewDecorationSerializer,
        allow_empty_type=True,
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDecorationNotSupported: ERROR_VIEW_DECORATION_NOT_SUPPORTED,
            DecoratorValueProviderTypeNotCompatible: ERROR_VIEW_DECORATION_VALUE_PROVIDER_NOT_COMPATIBLE,
        }
    )
    def post(self, request, data, view_id):
        """Creates a new decoration for the provided view."""

        view_handler = ViewHandler()
        view = view_handler.get_view(view_id)

        # We can safely assume the field exists because the
        # CreateViewDecorationSerializer has already checked that.
        view_decoration = action_type_registry.get_by_type(
            CreateDecorationActionType
        ).do(
            view,
            data["type"],
            data.get("value_provider_type", None),
            data.get("value_provider_conf", None),
            user=request.user,
        )

        serializer = ViewDecorationSerializer(view_decoration)
        return Response(serializer.data)


class ViewDecorationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_decoration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description=("Returns the view decoration related to the provided id."),
            )
        ],
        tags=["Database table view decorations"],
        operation_id="get_database_table_view_decoration",
        description=(
            "Returns the existing view decoration if the current user has access to "
            "the related database's workspace."
        ),
        responses={
            200: get_decoration_mapping_serializer(ViewDecorationSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DECORATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDecorationDoesNotExist: ERROR_VIEW_DECORATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, view_decoration_id):
        """Selects a single decoration and responds with a serialized version."""

        view_decoration = ViewHandler().get_decoration(request.user, view_decoration_id)
        serializer = ViewDecorationSerializer(view_decoration)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_decoration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the view decoration related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view decorations"],
        operation_id="update_database_table_view_decoration",
        description=(
            "Updates the existing decoration if the authorized user has access to the "
            "related database's workspace."
        ),
        request=get_decoration_mapping_serializer(UpdateViewDecorationSerializer),
        responses={
            200: get_decoration_mapping_serializer(ViewDecorationSerializer),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DECORATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDecorationDoesNotExist: ERROR_VIEW_DECORATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            DecoratorValueProviderTypeNotCompatible: ERROR_VIEW_DECORATION_VALUE_PROVIDER_NOT_COMPATIBLE,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, view_decoration_id):
        """Updates the view decoration."""

        handler = ViewHandler()
        view_decoration = handler.get_decoration(
            request.user,
            view_decoration_id,
            base_queryset=ViewDecoration.objects.select_for_update(of=("self",)),
        )

        type_name = request.data.get(
            "value_provider_type", view_decoration.value_provider_type
        )

        data = {**request.data}

        if (
            "value_provider_type" in data
            and data["value_provider_type"] != view_decoration.value_provider_type
        ):
            # If the value_provider_type is modified, we want to validate the
            # configuration with the new type so we add it to the data.
            data["value_provider_conf"] = data.get(
                "value_provider_conf", view_decoration.value_provider_conf
            )

        data = validate_data_custom_fields(
            type_name,
            decorator_value_provider_type_registry,
            data,
            type_attribute_name="value_provider_type",
            base_serializer_class=UpdateViewDecorationSerializer,
            allow_empty_type=True,
            partial=False,
        )

        action_type_registry.get_by_type(UpdateDecorationActionType).do(
            view_decoration,
            user=request.user,
            decorator_type_name=data.get("type", None),
            value_provider_type_name=data.get("value_provider_type", None),
            value_provider_conf=data.get("value_provider_conf", None),
            order=data.get("order", None),
        )

        serializer = ViewDecorationSerializer(view_decoration)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_decoration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the decoration related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view decorations"],
        operation_id="delete_database_table_view_decoration",
        description=(
            "Deletes the existing decoration if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DECORATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewDecorationDoesNotExist: ERROR_VIEW_DECORATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, view_decoration_id):
        """Deletes an existing decoration."""

        view_decoration = ViewHandler().get_decoration(request.user, view_decoration_id)

        workspace = view_decoration.view.table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            DeleteViewDecorationOperationType.type,
            workspace=workspace,
            context=view_decoration,
        )

        action_type_registry.get_by_type(DeleteDecorationActionType).do(
            view_decoration, user=request.user
        )

        return Response(status=204)


class ViewSortingsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only sortings of the view related to the provided "
                "value.",
            )
        ],
        tags=["Database table view sortings"],
        operation_id="list_database_table_view_sortings",
        description=(
            "Lists all sortings of the view related to the provided `view_id` if the "
            "user has access to the related database's workspace. A view can have "
            "multiple sortings. When all the rows are requested they will be in the "
            "desired order."
        ),
        responses={
            200: ViewSortSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_id):
        """
        Responds with a list of serialized sortings that belong to the view.
        """

        sortings = ViewHandler().list_sorts(request.user, view_id)
        serializer = ViewSortSerializer(sortings, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a sort for the view related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view sortings"],
        operation_id="create_database_table_view_sort",
        description=(
            "Creates a new sort for the view related to the provided `view_id` "
            "parameter if the authorized user has access to the related database's "
            "workspace. When the rows of a view are requested, for example via the "
            "`list_database_table_grid_view_rows` endpoint, they will be returned in "
            "the respected order defined by all the sortings."
        ),
        request=CreateViewSortSerializer(),
        responses={
            200: ViewSortSerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_VIEW_SORT_NOT_SUPPORTED",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS",
                    "ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(CreateViewSortSerializer)
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewSortNotSupported: ERROR_VIEW_SORT_NOT_SUPPORTED,
            ViewSortFieldAlreadyExist: ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS,
            ViewSortFieldNotSupported: ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED,
        }
    )
    def post(self, request, data, view_id):
        """Creates a new sort for the provided view."""

        view = ViewHandler().get_view(view_id)
        field = FieldHandler().get_field(data["field"])

        view_sort = action_type_registry.get_by_type(CreateViewSortActionType).do(
            request.user,
            view,
            field,
            data["order"],
            data.get("type"),
        )

        serializer = ViewSortSerializer(view_sort)
        return Response(serializer.data)


class ViewSortView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_sort_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the view sort related to the provided value.",
            )
        ],
        tags=["Database table view sortings"],
        operation_id="get_database_table_view_sort",
        description=(
            "Returns the existing view sort if the authorized user has access to the"
            " related database's workspace."
        ),
        responses={
            200: ViewSortSerializer(),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_SORT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewSortDoesNotExist: ERROR_VIEW_SORT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_sort_id):
        """Selects a single sort and responds with a serialized version."""

        view_sort = ViewHandler().get_sort(request.user, view_sort_id)
        serializer = ViewSortSerializer(view_sort)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_sort_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the view sort related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view sortings"],
        operation_id="update_database_table_view_sort",
        description=(
            "Updates the existing sort if the authorized user has access to the "
            "related database's workspace."
        ),
        request=UpdateViewSortSerializer(),
        responses={
            200: ViewSortSerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_SORT_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateViewSortSerializer)
    @map_exceptions(
        {
            ViewSortDoesNotExist: ERROR_VIEW_SORT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewSortFieldAlreadyExist: ERROR_VIEW_SORT_FIELD_ALREADY_EXISTS,
            ViewSortFieldNotSupported: ERROR_VIEW_SORT_FIELD_NOT_SUPPORTED,
        }
    )
    def patch(self, request, data, view_sort_id):
        """Updates the view sort."""

        handler = ViewHandler()
        view_sort = handler.get_sort(
            request.user,
            view_sort_id,
            base_queryset=ViewSort.objects.select_for_update(of=("self",)),
        )

        if "field" in data:
            # We can safely assume the field exists because the
            # UpdateViewSortSerializer has already checked that.
            data["field"] = Field.objects.get(pk=data["field"])

        view_sort = action_type_registry.get_by_type(UpdateViewSortActionType).do(
            request.user,
            view_sort,
            data.get("field"),
            data.get("order"),
            data.get("type"),
        )

        serializer = ViewSortSerializer(view_sort)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_sort_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the sort related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view sortings"],
        operation_id="delete_database_table_view_sort",
        description=(
            "Deletes the existing sort if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_SORT_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewSortDoesNotExist: ERROR_VIEW_SORT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, view_sort_id):
        """Deletes an existing sort."""

        view_sort = ViewHandler().get_sort(request.user, view_sort_id)
        action_type_registry.get_by_type(DeleteViewSortActionType).do(
            request.user, view_sort
        )

        return Response(status=204)


class ViewFieldOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            # Should be `AllowAny` because the field options can be requested in a
            # template that contains a form view for example.
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Responds with field options related to the provided "
                "value.",
            )
        ],
        tags=["Database table views"],
        operation_id="get_database_table_view_field_options",
        description="Responds with the fields options of the provided view if the "
        "authenticated user has access to the related workspace.",
        responses={
            200: view_field_options_mapping_serializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            ViewDoesNotSupportFieldOptions: ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS,
        }
    )
    def get(self, request, view_id):
        """Returns the field options of the view."""

        view = ViewHandler().get_view(view_id).specific

        view_type = ViewHandler().get_field_options_as_user(request.user, view)
        try:
            serializer_class = view_type.get_field_options_serializer_class(
                create_if_missing=True
            )
        except ValueError as exc:
            raise ViewDoesNotSupportFieldOptions(
                "The view type does not have a `field_options_serializer_class`"
            ) from exc
        return Response(serializer_class(view).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the field options related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="update_database_table_view_field_options",
        description="Updates the field options of a view. The field options differ "
        "per field type  This could for example be used to update the field width of "
        "a `grid` view if the user changes it.",
        request=view_field_options_mapping_serializer,
        responses={
            200: view_field_options_mapping_serializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UnrelatedFieldError: ERROR_UNRELATED_FIELD,
            ViewDoesNotSupportFieldOptions: ERROR_VIEW_DOES_NOT_SUPPORT_FIELD_OPTIONS,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
        }
    )
    def patch(self, request: Request, view_id: int) -> Response:
        """Updates the field option of the view."""

        handler = ViewHandler()
        view = handler.get_view(view_id).specific
        view_type = view_type_registry.get_by_model(view)
        serializer_class = view_type.get_field_options_serializer_class()
        data = validate_data(serializer_class, request.data, return_validated=True)

        with view_type.map_api_exceptions():
            action_type_registry.get_by_type(UpdateViewFieldOptionsActionType).do(
                request.user, view, field_options=data
            )

        serializer = serializer_class(view)
        return Response(serializer.data)


class RotateViewSlugView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="Rotates the slug of the view related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="rotate_database_view_slug",
        description=(
            "Rotates the unique slug of the view by replacing it with a new "
            "value. This would mean that the publicly shared URL of the view will "
            "change. Anyone with the old URL won't be able to access the view"
            "anymore. Only view types which are sharable can have their slugs rotated."
        ),
        request=None,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                view_type_registry,
                ViewSerializer,
            ),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_CANNOT_SHARE_VIEW_TYPE"]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CannotShareViewTypeError: ERROR_CANNOT_SHARE_VIEW_TYPE,
        }
    )
    @transaction.atomic
    def post(self, request: Request, view_id: int) -> Response:
        """Rotates the slug of a view."""

        view = action_type_registry.get_by_type(RotateViewSlugActionType).do(
            request.user,
            ViewHandler().get_view_for_update(request.user, view_id).specific,
        )

        serializer = view_type_registry.get_serializer(
            view, ViewSerializer, context={"user": request.user}
        )
        return Response(serializer.data)


class PublicViewLinkRowFieldLookupView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug related to the view.",
            ),
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="The field id of the link row field.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided only rows with data that matches the search "
                "query are going to be returned.",
            ),
            SEARCH_MODE_API_PARAM,
        ],
        tags=["Database table views"],
        operation_id="database_table_public_view_link_row_field_lookup",
        description=(
            "If the view is publicly shared or if an authenticated user has access to "
            "the related workspace, then this endpoint can be used to do a value "
            "lookup of the link row fields that are included in the view. Normally it "
            "is not possible for a not authenticated visitor to fetch the rows of a "
            "table. This endpoint makes it possible to fetch the id and primary field "
            "value of the related table of a link row included in the view."
        ),
        responses={
            200: get_example_pagination_serializer_class(LinkRowValueSerializer),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(
                ["ERROR_VIEW_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
        }
    )
    @validate_query_parameters(SearchQueryParamSerializer, return_validated=True)
    def get(self, request: Request, slug: str, field_id: int, query_params) -> Response:
        handler = ViewHandler()
        view = handler.get_public_view_by_slug(
            request.user,
            slug,
            authorization_token=get_public_view_authorization_token(request),
        ).specific
        view_type = view_type_registry.get_by_model(view)

        if not view_type.can_share:
            raise ViewDoesNotExist("View does not exist.")

        link_row_field_content_type = ContentType.objects.get_for_model(LinkRowField)

        try:
            queryset = view_type.get_visible_field_options_in_order(view)
            field_option = queryset.get(
                field_id=field_id, field__content_type=link_row_field_content_type
            )
        except ObjectDoesNotExist as exc:
            raise FieldDoesNotExist("The view field option does not exist.") from exc

        search = query_params.get("search")
        search_mode = query_params.get("search_mode")
        link_row_field = field_option.field.specific
        table = link_row_field.link_row_table
        primary_field = table.field_set.filter(primary=True).first()
        model = table.get_model()
        queryset = model.objects.all().enhance_by_fields()

        # If the link row field is limited to a specific view, then we must
        # apply those filters to prevent leaking rows that don't match those filters.
        if link_row_field.link_row_limit_selection_view_id is not None:
            view_handler = ViewHandler()
            limit_selection_specific_view = (
                link_row_field.link_row_limit_selection_view.specific
            )
            queryset = view_handler.apply_filters(
                limit_selection_specific_view, queryset
            )

        # If the view type needs the link row values to be restricted, we must figure
        # out which relations the view actually has to figure so that we can restrict
        # the queryset.
        if view_type.restrict_link_row_public_view_sharing:
            # If it's possible to filter in this view, we need to apply the filters
            # to make sure that the visitor can only request values that are actually
            # visible in the view.
            if view_type.can_filter:
                # We need the full model in order to apply all the filters.
                view_model = view.table.get_model()
                view_queryset = view_model.objects.all().enhance_by_fields()
                view_queryset = handler.apply_filters(view, view_queryset)
            else:
                view_model = view.table.get_model(fields=[link_row_field])
                view_queryset = view_model.objects.all().enhance_by_fields()

            view_queryset = view_queryset.values_list(f"field_{link_row_field.id}__id")
            queryset = queryset.filter(id__in=view_queryset)

        if search:
            queryset = queryset.search_all_fields(
                search,
                search_mode=search_mode,
                only_search_by_field_ids=[primary_field.id],
            )

        paginator = PageNumberPagination(limit_page_size=settings.ROW_PAGE_SIZE_LIMIT)
        page = paginator.paginate_queryset(queryset, request, self)
        serializer = LinkRowValueSerializer(
            page,
            many=True,
        )
        return paginator.get_paginated_response(serializer.data)


class PublicViewAuthView(APIView):
    """
    This view is used to authenticate an user against a password
    protected shared view.
    The user must provide the same password that the owner of the view
    has set up for the public shared link, otherwise an AuthenticationFailed
    error is returned.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug of the grid view to get public information "
                "about.",
            )
        ],
        tags=["Database table views"],
        operation_id="public_view_token_auth",
        description=(
            "Returns a valid never-expiring JWT token for this public shared view "
            "if the password provided matches with the one saved by the view's owner."
        ),
        request=PublicViewAuthRequestSerializer,
        responses={
            200: PublicViewAuthResponseSerializer,
            401: {"description": "The password provided for this view is incorrect"},
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(PublicViewAuthRequestSerializer)
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
        }
    )
    def post(self, request: Request, slug: str, data: Dict[str, Any]) -> Response:
        """
        Get the requested view and check the provided password.

        :param request: The request object.
        :param slug: The slug of the view to get public information about.
        :param data: The request data containing the password to access this view.
        :return: A valid JWT token if the password is correct, otherwise raise an
            AuthenticationFailed exception.
        """

        handler = ViewHandler()
        view = handler.get_public_view_by_slug(
            request.user, slug, raise_authorization_error=False
        )

        if not view.check_public_view_password(data["password"]):
            raise AuthenticationFailed()

        access_token = handler.encode_public_view_token(view)
        serializer = PublicViewAuthResponseSerializer({"access_token": access_token})
        return Response(serializer.data)


class PublicViewInfoView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug of the view to get public information " "about.",
            )
        ],
        tags=["Database table views"],
        operation_id="get_public_view_info",
        description=(
            "Returns the required public information to display a single "
            "shared view."
        ),
        request=None,
        responses={
            200: PublicViewInfoSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
        }
    )
    @transaction.atomic
    def get(self, request: Request, slug: str) -> Response:
        handler = ViewHandler()
        view = handler.get_public_view_by_slug(
            request.user,
            slug,
            authorization_token=get_public_view_authorization_token(request),
        )
        view_specific = view.specific
        view_type = view_type_registry.get_by_model(view_specific)

        if not view_type.has_public_info:
            raise ViewDoesNotExist()

        field_options = view_type.get_visible_field_options_in_order(view_specific)
        fields = specific_iterator(
            Field.objects.filter(id__in=field_options.values_list("field_id"))
            .select_related("content_type")
            .prefetch_related("select_options")
        )

        return Response(
            PublicViewInfoSerializer(
                view=view,
                fields=fields,
            ).data
        )


class ViewGroupBysView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only groupings of the view related to the "
                "provided value.",
            )
        ],
        tags=["Database table view groupings"],
        operation_id="list_database_table_view_groupings",
        description=(
            "Lists all groupings of the view related to the provided `view_id` if the "
            "user has access to the related database's workspace. A view can have "
            "multiple groupings."
        ),
        responses={
            200: ViewGroupBySerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_id):
        """
        Responds with a list of serialized groupings that belong to the view if the user
        has access to that workspace.
        """

        groupings = ViewHandler().list_group_bys(request.user, view_id)
        serializer = ViewGroupBySerializer(groupings, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a group by for the view related to the provided "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view groupings"],
        operation_id="create_database_table_view_group",
        description=(
            "Creates a new group by for the view related to the provided `view_id` "
            "parameter if the authorized user has access to the related database's "
            "workspace."
        ),
        request=CreateViewGroupBySerializer(),
        responses={
            200: ViewGroupBySerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_VIEW_GROUP_BY_NOT_SUPPORTED",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS",
                    "ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(CreateViewGroupBySerializer)
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewGroupByNotSupported: ERROR_VIEW_GROUP_BY_NOT_SUPPORTED,
            ViewGroupByFieldAlreadyExist: ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS,
            ViewGroupByFieldNotSupported: ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED,
        }
    )
    def post(self, request, data, view_id):
        """Creates a new group by for the provided view."""

        view = ViewHandler().get_view(view_id)
        field = FieldHandler().get_field(data["field"]).specific

        view_group_by = action_type_registry.get_by_type(
            CreateViewGroupByActionType
        ).do(request.user, view, field, data["order"], data["width"], data.get("type"))

        serializer = ViewGroupBySerializer(view_group_by)
        return Response(serializer.data)


class ViewGroupByView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_group_by_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the view group by related to the provided value.",
            )
        ],
        tags=["Database table view groupings"],
        operation_id="get_database_table_view_group",
        description=(
            "Returns the existing view group by if the authorized user has access to "
            "the related database's workspace."
        ),
        responses={
            200: ViewGroupBySerializer(),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewGroupByDoesNotExist: ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, view_group_by_id):
        """Selects a single group by and responds with a serialized version."""

        view_group_by = ViewHandler().get_group_by(request.user, view_group_by_id)
        serializer = ViewGroupBySerializer(view_group_by)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_group_by_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the view group by related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view groupings"],
        operation_id="update_database_table_view_group",
        description=(
            "Updates the existing group by if the authorized user has access to the "
            "related database's workspace."
        ),
        request=UpdateViewGroupBySerializer(),
        responses={
            200: ViewGroupBySerializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateViewGroupBySerializer)
    @map_exceptions(
        {
            ViewGroupByDoesNotExist: ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            ViewGroupByFieldAlreadyExist: ERROR_VIEW_GROUP_BY_FIELD_ALREADY_EXISTS,
            ViewGroupByFieldNotSupported: ERROR_VIEW_GROUP_BY_FIELD_NOT_SUPPORTED,
        }
    )
    def patch(self, request, data, view_group_by_id):
        """Updates the view group by."""

        handler = ViewHandler()
        view_group_by = handler.get_group_by(
            request.user,
            view_group_by_id,
            base_queryset=ViewGroupBy.objects.select_for_update(of=("self",)),
        )

        if "field" in data:
            # We can safely assume the field exists because the
            # UpdateViewGroupBySerializer has already checked that.
            data["field"] = Field.objects.get(pk=data["field"])

        view_group_by = action_type_registry.get_by_type(
            UpdateViewGroupByActionType
        ).do(
            request.user,
            view_group_by,
            data.get("field"),
            data.get("order"),
            data.get("width"),
            data.get("type"),
        )

        serializer = ViewGroupBySerializer(view_group_by)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_group_by_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the group by related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table view groupings"],
        operation_id="delete_database_table_view_group",
        description=(
            "Deletes the existing group by if the authorized user has access to the "
            "related database's workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ViewGroupByDoesNotExist: ERROR_VIEW_GROUP_BY_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, view_group_by_id):
        """Deletes an existing group by."""

        view_group_by = ViewHandler().get_group_by(request.user, view_group_by_id)
        action_type_registry.get_by_type(DeleteViewGroupByActionType).do(
            request.user, view_group_by
        )

        return Response(status=204)


class PublicViewGetRowView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug of the view from which to get the row data.",
            ),
            OpenApiParameter(
                name="row_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="The ID of the row to retrieve from the public view.",
            ),
        ],
        tags=["Database table views"],
        operation_id="get_public_view_row",
        description=(
            "Returns the data for a specific row in a publicly shared view, "
            "identified by the view’s slug and the row’s ID."
        ),
        request=None,
        responses={
            200: get_example_row_serializer_class(
                example_type="public_get", user_field_names=True
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(
                ["ERROR_VIEW_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            ViewDoesNotSupportListingRows: ERROR_VIEW_DOES_NOT_SUPPORT_LISTING_ROWS,
        }
    )
    def get(self, request: Request, slug: str, row_id: int) -> Response:
        handler = ViewHandler()
        view = handler.get_public_view_by_slug(
            request.user,
            slug,
            authorization_token=get_public_view_authorization_token(request),
        ).specific

        queryset, field_ids, _ = handler.get_public_rows_queryset_and_field_ids(view)

        row = queryset.filter(id=row_id).first()
        if row is None:
            raise RowDoesNotExist("The row does not exist in the view.")

        serializer_class = get_row_serializer_class(
            row._meta.model, RowSerializer, is_response=True, field_ids=field_ids
        )
        return Response(serializer_class(row).data)
