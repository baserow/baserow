from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.contrib.dashboard.api.errors import (
    ERROR_DASHBOARD_DOES_NOT_EXIST,
    ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD,
)
from baserow.contrib.dashboard.api.public.utils import (
    get_public_dashboard_authorization_token,
)
from baserow.contrib.dashboard.api.widgets.errors import (
    ERROR_WIDGET_DOES_NOT_EXIST,
    ERROR_WIDGET_IMPROPERLY_CONFIGURED,
)
from baserow.contrib.dashboard.exceptions import (
    DashboardDoesNotExist,
    NoAuthorizationToPublicDashboard,
)
from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.options import DashboardWidgetOptionsService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.database.table.exceptions import TableDoesNotExist


class WidgetOptionsSerializer(serializers.Serializer):
    results = serializers.ListField(child=serializers.CharField())


class WidgetOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Dashboard widgets"],
        operation_id="get_dashboard_widget_options",
        responses={200: WidgetOptionsSerializer},
    )
    @map_exceptions(
        {
            WidgetDoesNotExist: ERROR_WIDGET_DOES_NOT_EXIST,
            TableDoesNotExist: ERROR_WIDGET_IMPROPERLY_CONFIGURED,
        }
    )
    def get(self, request, widget_id):
        widget = WidgetService().get_widget(request.user, widget_id)
        return Response(
            {"results": DashboardWidgetOptionsService().get_options(widget)}
        )


class PublicWidgetOptionsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Dashboard public"],
        operation_id="get_public_dashboard_widget_options",
        responses={200: WidgetOptionsSerializer},
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            NoAuthorizationToPublicDashboard: ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD,
            WidgetDoesNotExist: ERROR_WIDGET_DOES_NOT_EXIST,
            TableDoesNotExist: ERROR_WIDGET_IMPROPERLY_CONFIGURED,
        }
    )
    def get(self, request, slug, widget_id):
        dashboard = DashboardHandler().get_public_dashboard_by_slug(
            request.user,
            slug,
            authorization_token=get_public_dashboard_authorization_token(request),
        )
        widget = WidgetHandler().get_widget(
            widget_id, base_queryset=Widget.objects.filter(dashboard=dashboard)
        )
        return Response(
            {"results": DashboardWidgetOptionsService().get_options(widget)}
        )
