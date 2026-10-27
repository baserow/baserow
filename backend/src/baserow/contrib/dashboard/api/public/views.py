from typing import Any, Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.contrib.dashboard.api.data_sources.errors import (
    ERROR_DASHBOARD_DATA_DOES_NOT_EXIST,
    ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST,
    ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
)
from baserow.contrib.dashboard.api.errors import (
    ERROR_DASHBOARD_DOES_NOT_EXIST,
    ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD,
)
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.exceptions import (
    DashboardDoesNotExist,
    NoAuthorizationToPublicDashboard,
)
from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.core.services.exceptions import (
    DoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
)

from .serializers import (
    PublicDashboardAuthInfoSerializer,
    PublicDashboardAuthRequestSerializer,
    PublicDashboardAuthResponseSerializer,
    PublicDashboardInfoSerializer,
)
from .utils import get_public_dashboard_authorization_token

SLUG_PARAMETER = OpenApiParameter(
    name="slug",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.STR,
    required=True,
    description="The slug of the publicly shared dashboard.",
)


class PublicDashboardInfoView(APIView):
    """
    Returns what a visitor needs to render a publicly shared dashboard. Workspace
    members who can read the dashboard may use it as well, even when the
    dashboard is private or password protected, exactly like publicly shared
    views.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Dashboard public"],
        operation_id="get_public_dashboard_info",
        description=(
            "Returns the dashboard, its widgets and its data sources of a publicly "
            "shared dashboard. Only the information needed to render the dashboard "
            "is included, never the configuration of the data sources."
        ),
        request=None,
        responses={
            200: PublicDashboardInfoSerializer,
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"]),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            NoAuthorizationToPublicDashboard: ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD,
        }
    )
    def get(self, request: Request, slug: str) -> Response:
        dashboard = DashboardHandler().get_public_dashboard_by_slug(
            request.user,
            slug,
            authorization_token=get_public_dashboard_authorization_token(request),
        )
        widgets = WidgetHandler().get_widgets(dashboard)
        data_sources = DashboardDataSourceHandler().get_data_sources(dashboard)

        return Response(
            PublicDashboardInfoSerializer(
                dashboard,
                context={"widgets": widgets, "data_sources": data_sources},
            ).data
        )


class PublicDashboardAuthView(APIView):
    """
    Exchanges the password of a password protected public dashboard for a
    non-expiring token that must be sent in the
    `PUBLIC_DASHBOARD_AUTHORIZATION_HEADER` of the other public endpoints. Also
    tells the password page what it may show before the password is known.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Dashboard public"],
        operation_id="get_public_dashboard_auth_info",
        description=(
            "Returns what the password page of a publicly shared dashboard needs "
            "before the password is entered, currently whether the Baserow logo "
            "must be shown. Nothing about the dashboard itself is revealed."
        ),
        request=None,
        responses={
            200: PublicDashboardAuthInfoSerializer,
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, slug: str) -> Response:
        dashboard = DashboardHandler().get_public_dashboard_by_slug(
            request.user, slug, raise_authorization_error=False
        )
        return Response(
            PublicDashboardAuthInfoSerializer({"show_logo": dashboard.show_logo}).data
        )

    @extend_schema(
        parameters=[SLUG_PARAMETER],
        tags=["Dashboard public"],
        operation_id="public_dashboard_token_auth",
        description=(
            "Returns a valid never-expiring JWT token for this publicly shared "
            "dashboard if the password provided matches with the one saved by the "
            "dashboard's owner."
        ),
        request=PublicDashboardAuthRequestSerializer,
        responses={
            200: PublicDashboardAuthResponseSerializer,
            401: {
                "description": "The password provided for this dashboard is incorrect"
            },
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(PublicDashboardAuthRequestSerializer)
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def post(self, request: Request, slug: str, data: Dict[str, Any]) -> Response:
        handler = DashboardHandler()
        dashboard = handler.get_public_dashboard_by_slug(
            request.user, slug, raise_authorization_error=False
        )

        if not dashboard.check_public_password(data["password"]):
            raise AuthenticationFailed()

        access_token = handler.encode_public_access_token(dashboard)
        return Response(
            PublicDashboardAuthResponseSerializer({"access_token": access_token}).data
        )


class PublicDashboardDataSourceDispatchView(APIView):
    """
    Dispatches a data source of a publicly shared dashboard. The dispatch happens
    at handler level, like it does for publicly shared views, because visitors
    have no permissions in the workspace.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            SLUG_PARAMETER,
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="The id of the data source of the dashboard to dispatch.",
            ),
        ],
        tags=["Dashboard public"],
        operation_id="dispatch_public_dashboard_data_source",
        description=(
            "Dispatches the service of the related data source of the publicly "
            "shared dashboard and returns the result."
        ),
        request=None,
        responses={
            400: get_error_schema(
                ["ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED"]
            ),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"]),
            404: get_error_schema(
                [
                    "ERROR_DASHBOARD_DOES_NOT_EXIST",
                    "ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST",
                    "ERROR_DASHBOARD_DATA_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            NoAuthorizationToPublicDashboard: ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD,
            DashboardDataSourceDoesNotExist: ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST,
            DashboardDataSourceImproperlyConfigured: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
            ServiceImproperlyConfiguredDispatchException: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
            DoesNotExist: ERROR_DASHBOARD_DATA_DOES_NOT_EXIST,
        }
    )
    def post(self, request: Request, slug: str, data_source_id: int) -> Response:
        dashboard = DashboardHandler().get_public_dashboard_by_slug(
            request.user,
            slug,
            authorization_token=get_public_dashboard_authorization_token(request),
        )

        handler = DashboardDataSourceHandler()
        # Only data sources of this dashboard can be dispatched through its slug.
        data_source = handler.get_data_source(
            data_source_id,
            base_queryset=DashboardDataSource.objects.filter(dashboard=dashboard),
        )

        dispatch_context = DashboardDispatchContext(
            request, dashboard.workspace, dashboard=dashboard
        )
        return Response(handler.dispatch_data_source(data_source, dispatch_context))
