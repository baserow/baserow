from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.contrib.dashboard.api.data_sources.errors import (
    ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.filters.exceptions import (
    DashboardFilterDoesNotExist,
    DashboardFilterOptionsExpired,
    DashboardFilterOptionsTooLarge,
)
from baserow.contrib.dashboard.filters.options import DashboardFilterOptionsService
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

from .errors import (
    ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST,
    ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED,
    ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE,
)
from .serializers import DashboardFilterSelectionField


class DashboardFilterOptionsRequestSerializer(serializers.Serializer):
    after = serializers.CharField(
        required=False,
        allow_null=True,
        trim_whitespace=False,
        help_text=(
            "A continuation cursor, or the snapshot cursor to check selected-value "
            "availability against previously loaded choices."
        ),
    )
    limit = serializers.IntegerField(min_value=1, max_value=100, default=50)
    selected = DashboardFilterSelectionField(
        child=serializers.CharField(trim_whitespace=False),
        required=False,
        default=list,
    )


class DashboardFilterOptionsResponseSerializer(serializers.Serializer):
    results = serializers.ListField(child=serializers.CharField())
    next = serializers.CharField(allow_null=True)
    snapshot = serializers.CharField(
        help_text=(
            "A cursor to the first page of these choices, including when next is null. "
            "Pass it as after to recheck selected-value availability without resolving "
            "the option formula again."
        )
    )
    available = serializers.ListField(child=serializers.CharField())


class DashboardFilterOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Dashboard filters"],
        operation_id="list_dashboard_filter_options",
        request=DashboardFilterOptionsRequestSerializer,
        responses={
            200: DashboardFilterOptionsResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED",
                    "ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE",
                    "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED",
                ]
            ),
        },
        description="Resolve filter values from a table field or formula. Selected-value availability is independent of pagination.",
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardFilterDoesNotExist: ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST,
            DashboardFilterOptionsExpired: ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED,
            DashboardFilterOptionsTooLarge: ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE,
            DashboardDataSourceImproperlyConfigured: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
            ServiceImproperlyConfiguredDispatchException: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
        }
    )
    @validate_body(DashboardFilterOptionsRequestSerializer, return_validated=True)
    def post(self, request, filter_id, data):
        return Response(
            DashboardFilterOptionsService().get_options(
                request.user, filter_id, request, **data
            )
        )
