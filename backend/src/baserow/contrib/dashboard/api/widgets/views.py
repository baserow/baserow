from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body_custom_fields
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    validate_data_custom_fields,
)
from baserow.contrib.dashboard.api.errors import ERROR_DASHBOARD_DOES_NOT_EXIST
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
)
from baserow.contrib.dashboard.widgets.exceptions import (
    WidgetDoesNotExist,
    WidgetImproperlyConfigured,
    WidgetTypeDoesNotExist,
)
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.contrib.dashboard.widgets.service import WidgetService

from .errors import (
    ERROR_WIDGET_DOES_NOT_EXIST,
    ERROR_WIDGET_IMPROPERLY_CONFIGURED,
    ERROR_WIDGET_TYPE_DOES_NOT_EXIST,
)
from .serializers import (
    CreateWidgetSerializer,
    UpdateWidgetSerializer,
    WidgetSerializer,
)


class WidgetsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the widgets of the dashboard related to the "
                "provided Id.",
            )
        ],
        tags=["Dashboard widgets"],
        operation_id="list_dashboard_widgets",
        description=(
            "Lists all the widgets of the dashboard related to the provided parameter if "
            "the user has access to the related workspace. "
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                widget_type_registry, WidgetSerializer, many=True
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def get(self, request, dashboard_id):
        """
        Responds with a list of serialized widgets that belong to the dashboard
        if the user has access to that page.
        """

        widgets = WidgetService().get_widgets(request.user, dashboard_id)
        data = [
            widget_type_registry.get_serializer(widget, WidgetSerializer).data
            for widget in widgets
        ]
        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a widget for the dashboard related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard widgets"],
        operation_id="create_dashboard_widget",
        description="Creates a new dashboard widget",
        request=DiscriminatorCustomFieldsMappingSerializer(
            widget_type_registry,
            CreateWidgetSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                widget_type_registry, WidgetSerializer
            ),
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_WIDGET_TYPE_DOES_NOT_EXIST"]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_DASHBOARD_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
            WidgetTypeDoesNotExist: ERROR_WIDGET_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_body_custom_fields(
        widget_type_registry, base_serializer_class=CreateWidgetSerializer
    )
    def post(self, request, data: Dict, dashboard_id: int):
        """Creates a new widget."""

        widget_type = data.pop("type")
        widget = CreateWidgetActionType.do(
            request.user, dashboard_id, widget_type, data
        )
        serializer = widget_type_registry.get_serializer(widget, WidgetSerializer)
        return Response(serializer.data)


class WidgetView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="widget_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the widget",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard widgets"],
        operation_id="update_dashboard_widget",
        description="Updates an existing dashboard widget.",
        request=CustomFieldRegistryMappingSerializer(
            widget_type_registry,
            UpdateWidgetSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                widget_type_registry, WidgetSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_WIDGET_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WidgetDoesNotExist: ERROR_WIDGET_DOES_NOT_EXIST,
            WidgetImproperlyConfigured: ERROR_WIDGET_IMPROPERLY_CONFIGURED,
        }
    )
    def patch(self, request, widget_id: int):
        """
        Update a dashboard widget.
        """

        widget = WidgetService().get_widget(request.user, widget_id)
        widget_type = widget.get_type().type
        data = validate_data_custom_fields(
            widget_type,
            widget_type_registry,
            request.data,
            base_serializer_class=UpdateWidgetSerializer,
            partial=True,
            return_validated=True,
        )
        updated_widget = UpdateWidgetActionType.do(
            request.user, widget_id, widget_type, data
        )
        serializer = widget_type_registry.get_serializer(
            updated_widget, WidgetSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="widget_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the widget",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard widgets"],
        operation_id="delete_dashboard_widget",
        description="Deletes the widget related to the given id.",
        responses={
            204: None,
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_WIDGET_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WidgetDoesNotExist: ERROR_WIDGET_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, widget_id: int):
        """
        Deletes a widget.
        """

        DeleteWidgetActionType.do(request.user, widget_id)
        return Response(status=204)
