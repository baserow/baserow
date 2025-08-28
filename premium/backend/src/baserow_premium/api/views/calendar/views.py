from django.conf import settings
from django.db import transaction
from django.http import HttpResponse

from baserow_premium.api.views.calendar.errors import (
    ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD,
)
from baserow_premium.api.views.calendar.serializers import (
    ListCalendarRowsQueryParamsSerializer,
    get_calendar_view_example_response_serializer,
)
from baserow_premium.ical_utils import build_calendar
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.views.actions import RotateCalendarIcalSlugActionType
from baserow_premium.views.exceptions import CalendarViewHasNoDateField
from baserow_premium.views.handler import get_rows_grouped_by_date_field
from baserow_premium.views.models import CalendarView
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
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.database.api.constants import (
    ADHOC_FILTERS_API_PARAMS,
    ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
    LIMIT_LINKED_ITEMS_API_PARAM,
    SEARCH_MODE_API_PARAM,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FILTER_FIELD_NOT_FOUND,
)
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_CANNOT_SHARE_VIEW_TYPE,
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.serializers import ViewSerializer
from baserow.contrib.database.api.views.utils import (
    get_public_view_authorization_token,
    parse_limit_linked_items_params,
)
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    FilterFieldNotFound,
)
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.views.exceptions import (
    CannotShareViewTypeError,
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.signals import view_loaded
from baserow.core.action.registries import action_type_registry
from baserow.core.db import specific_queryset
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler


class CalendarViewView(APIView):
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
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines how many rows per day should be returned by"
                " default. This value can be overwritten per select"
                " option.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines from which offset the rows should be returned.",
                default=0,
            ),
            OpenApiParameter(
                name="from_timestamp",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.DATETIME,
                description="Restricts results based on the calendar date field.",
                required=True,
            ),
            OpenApiParameter(
                name="to_timestamp",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.DATETIME,
                description="Restricts results based on the calendar date field.",
                required=True,
            ),
            OpenApiParameter(
                name="user_timezone",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="User's timezone will be taken into account for date field"
                "types that have a time and don't enforce a timezone. The timezone "
                "will be used for aggregating the dates. For date fields without a "
                "time this will be ignored and UTC will be forced. ",
                default="UTC",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided only rows with data that matches the search "
                "query are going to be returned.",
                required=False,
            ),
            SEARCH_MODE_API_PARAM,
            *ADHOC_FILTERS_API_PARAMS_NO_COMBINE,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table calendar view"],
        operation_id="list_database_table_calendar_view_rows",
        description=(
            "Responds with serialized rows grouped by date regarding view's date field"
            "if the user is authenticated and has access to the related "
            "workspace."
            "\n\nThis is a **premium** feature."
        ),
        responses={
            200: get_calendar_view_example_response_serializer(),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD",
                    "ERROR_FEATURE_NOT_AVAILABLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CalendarViewHasNoDateField: (ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD),
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
        }
    )
    @allowed_includes("field_options", "row_metadata")
    @validate_query_parameters(
        ListCalendarRowsQueryParamsSerializer, return_validated=True
    )
    def get(self, request, view_id, field_options, row_metadata, query_params):
        """
        Responds with the rows grouped by date.
        """

        view_handler = ViewHandler()
        view = view_handler.get_view_as_user(request.user, view_id, CalendarView)
        workspace = view.table.database.workspace

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

        date_field = view.date_field
        if not date_field:
            raise CalendarViewHasNoDateField(
                "The requested calendar view does not have a required date field."
            )

        model = view.table.get_model()
        adhoc_filters = AdHocFilters.from_request(request)

        grouped_rows = get_rows_grouped_by_date_field(
            user=request.user,
            view=view,
            date_field=date_field,
            from_timestamp=query_params.get("from_timestamp"),
            to_timestamp=query_params.get("to_timestamp"),
            user_timezone=query_params.get("user_timezone"),
            limit=query_params.get("limit"),
            offset=query_params.get("offset"),
            model=model,
            adhoc_filters=adhoc_filters,
            search=query_params.get("search"),
            search_mode=query_params.get("search_mode"),
            combine_filters=False,
        )

        limit_linked_items = parse_limit_linked_items_params(request)
        serializer_extra_kwargs = {"limit_linked_items": limit_linked_items}

        serializer_class = get_row_serializer_class(
            model, RowSerializer, is_response=True, extra_kwargs=serializer_extra_kwargs
        )

        grouped_rows_serialized = {}
        for key, value in grouped_rows.items():
            grouped_rows_serialized[key] = {
                "count": value["count"],
                "results": serializer_class(value["results"], many=True).data,
            }

        response = {"rows": grouped_rows_serialized}

        if field_options:
            view_type = view_type_registry.get_by_model(view)
            context = {"fields": [o["field"] for o in model._field_objects.values()]}
            serializer_class = view_type.get_field_options_serializer_class(
                create_if_missing=True
            )
            response.update(**serializer_class(view, context=context).data)

        if row_metadata:
            row_metadata = row_metadata_registry.generate_and_merge_metadata_for_rows(
                request.user,
                view.table,
                (
                    row.id
                    for row_group in grouped_rows.values()
                    for row in row_group["results"]
                ),
            )
            response.update(row_metadata=row_metadata)

        view_loaded.send(
            sender=self,
            table=view.table,
            view=view,
            table_model=model,
            user=request.user,
        )
        return Response(response)


class PublicCalendarViewView(APIView):
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
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines how many rows per day should be returned by"
                " default. This value can be overwritten per select"
                " option.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines from which offset the rows should be returned."
                "This value can be overwritten per select option.",
            ),
            OpenApiParameter(
                name="from_timestamp",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.DATETIME,
                description="Restricts results based on the calendar date field.",
                required=True,
            ),
            OpenApiParameter(
                name="to_timestamp",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.DATETIME,
                description="Restricts results based on the calendar date field.",
                required=True,
            ),
            OpenApiParameter(
                name="user_timezone",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="User's timezone will be taken into account for date field"
                "types that have a time and don't enforce a timezone. The timezone "
                "will be used for aggregating the dates. For date fields without a "
                "time this will be ignored and UTC will be forced. ",
                default="UTC",
                required=False,
            ),
            *ADHOC_FILTERS_API_PARAMS,
            LIMIT_LINKED_ITEMS_API_PARAM,
        ],
        tags=["Database table calendar view"],
        operation_id="public_list_database_table_calendar_view_rows",
        description=(
            "Responds with serialized rows grouped by the view's date field "
            "options related to the `slug` if the calendar view is publicly shared. "
            "Additional query parameters can be provided to control the `limit` and "
            "`offset` per select option. \n\nThis is a **premium** feature."
        ),
        responses={
            200: get_calendar_view_example_response_serializer(),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            400: get_error_schema(
                [
                    "ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_FILTERS_PARAM_VALIDATION_ERROR",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CalendarViewHasNoDateField: ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD,
            NoAuthorizationToPubliclySharedView: (
                ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW
            ),
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
        }
    )
    @allowed_includes("field_options")
    @validate_query_parameters(
        ListCalendarRowsQueryParamsSerializer, return_validated=True
    )
    def get(self, request, slug: str, field_options: bool, query_params):
        view_handler = ViewHandler()
        view = view_handler.get_public_view_by_slug(
            request.user,
            slug,
            CalendarView,
            authorization_token=get_public_view_authorization_token(request),
        )

        date_field = view.date_field
        if not date_field:
            raise CalendarViewHasNoDateField(
                "The requested calendar view does not have a required date field."
            )

        model = view.table.get_model()

        adhoc_filters = AdHocFilters.from_request(request)

        view_type = view_type_registry.get_by_model(view)
        (
            _,  # fields queryset, not used
            field_ids,
            publicly_visible_field_options,
        ) = ViewHandler().get_public_rows_queryset_and_field_ids(
            view,
            table_model=model,
            view_type=view_type,
        )

        grouped_rows = get_rows_grouped_by_date_field(
            user=None,
            view=view,
            date_field=date_field,
            from_timestamp=query_params.get("from_timestamp"),
            to_timestamp=query_params.get("to_timestamp"),
            user_timezone=query_params.get("user_timezone"),
            limit=query_params.get("limit"),
            offset=query_params.get("offset"),
            model=model,
            adhoc_filters=adhoc_filters,
            combine_filters=True,
        )

        limit_linked_items = parse_limit_linked_items_params(request)
        serializer_extra_kwargs = {"limit_linked_items": limit_linked_items}

        serializer_class = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            field_ids=field_ids,
            extra_kwargs=serializer_extra_kwargs,
        )

        for key, value in grouped_rows.items():
            grouped_rows[key]["results"] = serializer_class(
                value["results"], many=True
            ).data

        response = {"rows": grouped_rows}

        if field_options:
            context = {"field_options": publicly_visible_field_options}
            serializer_class = view_type.get_field_options_serializer_class(
                create_if_missing=True
            )
            response.update(**serializer_class(view, context=context).data)

        return Response(response)


class ICalView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="ical_slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="ICal feed unique slug.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="calendar_ical_feed",
        description=(
            "Returns ICal feed for a specific Calendar view "
            "identified by ical_slug value. "
            "Calendar View resource contains full url in .ical_feed_url "
            "field."
        ),
        request=None,
        responses={
            (200, "text/calendar"): OpenApiTypes.BINARY,
            400: get_error_schema(["ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            CalendarViewHasNoDateField: ERROR_CALENDAR_VIEW_HAS_NO_DATE_FIELD,
        }
    )
    def get(self, request, ical_slug: str):
        view_handler = ViewHandler()
        view: CalendarView = view_handler.get_view(
            view_id=ical_slug,
            view_model=CalendarView,
            base_queryset=specific_queryset(
                CalendarView.objects.select_related(
                    "date_field", "date_field__content_type", "table"
                ).prefetch_related("field_options")
            ),
            pk_field="ical_slug",
        )
        if not view.ical_public:
            raise ViewDoesNotExist()
        qs = view_handler.get_queryset(request.user, view)
        cal = build_calendar(qs, view, limit=settings.BASEROW_ICAL_VIEW_MAX_EVENTS)
        return HttpResponse(
            cal.to_ical(),
            content_type="text/calendar",
            headers={"Cache-Control": "max-age=1800"},
        )


class RotateIcalFeedSlugView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="Rotates the ical feed slug of the calendar view related to the provided "
                "id.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table views"],
        operation_id="rotate_calendar_view_ical_feed_slug",
        description=(
            "Rotates the unique slug of the calendar view's ical feed by replacing it "
            "with a new value. This would mean that the publicly shared URL of the "
            "view will change. Anyone with the old URL won't be able to access the "
            "view anymore."
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
        """Rotates the calendar's ical slug of a view."""

        view = action_type_registry.get_by_type(RotateCalendarIcalSlugActionType).do(
            request.user,
            ViewHandler().get_view_for_update(request.user, view_id).specific,
        )

        serializer = view_type_registry.get_serializer(
            view, ViewSerializer, context={"user": request.user}
        )
        return Response(serializer.data)
