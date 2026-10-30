from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.contrib.dashboard.api.errors import ERROR_DASHBOARD_DOES_NOT_EXIST
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.contrib.dashboard.filters.actions import (
    CreateDashboardFilterActionType,
    DeleteDashboardFilterActionType,
    OrderDashboardFiltersActionType,
    UpdateDashboardFilterActionType,
)
from baserow.contrib.dashboard.filters.exceptions import (
    DashboardFilterDoesNotExist,
    InvalidDashboardFilterConfiguration,
    InvalidDashboardFilterOrder,
    InvalidDashboardFilterValues,
)
from baserow.contrib.dashboard.filters.service import DashboardFilterService

from .errors import (
    ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST,
    ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION,
    ERROR_DASHBOARD_FILTER_INVALID_VALUES,
    ERROR_DASHBOARD_FILTER_ORDER_INVALID,
)
from .serializers import DashboardFilterSerializer, OrderDashboardFiltersSerializer


class DashboardFiltersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="list_dashboard_filters",
        description="List the saved filter configuration, including shared selections.",
        responses={
            200: DashboardFilterSerializer(many=True),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def get(self, request, dashboard_id):
        filters = DashboardFilterService().get_filters(request.user, dashboard_id)
        return Response(DashboardFilterSerializer(filters, many=True).data)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="create_dashboard_filter",
        description="Create a text, number, or date filter for a dashboard.",
        parameters=[
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        request=DashboardFilterSerializer,
        responses={
            200: DashboardFilterSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION",
                    "ERROR_DASHBOARD_FILTER_INVALID_VALUES",
                ]
            ),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            InvalidDashboardFilterConfiguration: ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION,
            InvalidDashboardFilterValues: ERROR_DASHBOARD_FILTER_INVALID_VALUES,
        }
    )
    @validate_body(DashboardFilterSerializer, return_validated=True)
    def post(self, request, dashboard_id, data):
        dashboard_filter = CreateDashboardFilterActionType.do(
            request.user, dashboard_id, data
        )
        return Response(DashboardFilterSerializer(dashboard_filter).data)


class OrderDashboardFiltersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="order_dashboard_filters",
        description="Change the order of the filters displayed on a dashboard.",
        parameters=[
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        request=OrderDashboardFiltersSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DASHBOARD_FILTER_ORDER_INVALID",
                ]
            ),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            InvalidDashboardFilterOrder: ERROR_DASHBOARD_FILTER_ORDER_INVALID,
        }
    )
    @validate_body(OrderDashboardFiltersSerializer, return_validated=True)
    def post(self, request, dashboard_id, data):
        OrderDashboardFiltersActionType.do(request.user, dashboard_id, data["order"])
        return Response(status=204)


class DashboardFilterView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="update_dashboard_filter",
        description="Update the shared configuration of a dashboard filter.",
        parameters=[
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        request=DashboardFilterSerializer,
        responses={
            200: DashboardFilterSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION",
                    "ERROR_DASHBOARD_FILTER_INVALID_VALUES",
                ]
            ),
            404: get_error_schema(["ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardFilterDoesNotExist: ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST,
            InvalidDashboardFilterConfiguration: ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION,
            InvalidDashboardFilterValues: ERROR_DASHBOARD_FILTER_INVALID_VALUES,
        }
    )
    @validate_body(DashboardFilterSerializer, partial=True, return_validated=True)
    def patch(self, request, filter_id, data):
        dashboard_filter = UpdateDashboardFilterActionType.do(
            request.user, filter_id, data
        )
        return Response(DashboardFilterSerializer(dashboard_filter).data)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="delete_dashboard_filter",
        description="Delete a dashboard filter. Its configuration can be restored with undo.",
        parameters=[
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        responses={
            204: None,
            404: get_error_schema(["ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {DashboardFilterDoesNotExist: ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST}
    )
    def delete(self, request, filter_id):
        DeleteDashboardFilterActionType.do(request.user, filter_id)
        return Response(status=204)
