from typing import Any, Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.contrib.dashboard.actions import (
    RotateDashboardSlugActionType,
    UpdateDashboardSharingActionType,
)
from baserow.contrib.dashboard.api.errors import ERROR_DASHBOARD_DOES_NOT_EXIST
from baserow.contrib.dashboard.api.serializers import (
    UpdateDashboardSharingSerializer,
)
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace


class RotateDashboardSlugView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="Rotates the slug of the dashboard related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard"],
        operation_id="rotate_dashboard_slug",
        description=(
            "Rotates the unique slug of the dashboard by replacing it with a new "
            "value. This changes the publicly shared URL of the dashboard, so anyone "
            "with the old URL won't be able to access the dashboard anymore."
        ),
        request=None,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def post(self, request: Request, dashboard_id: int) -> Response:
        """Rotates the public slug of a dashboard."""

        dashboard = action_type_registry.get_by_type(RotateDashboardSlugActionType).do(
            request.user, dashboard_id
        )
        return Response(PolymorphicApplicationResponseSerializer(dashboard).data)


class DashboardSharingView(APIView):
    """
    Changes the public sharing state of a dashboard. It has its own endpoint and
    action, instead of the generic application update, so the audit log can
    describe what changed. Hiding the Baserow logo is a premium attribute with
    its own endpoint.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                required=True,
                description="Updates the sharing state of the dashboard related "
                "to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard"],
        operation_id="update_dashboard_sharing",
        description=(
            "Makes the dashboard publicly accessible via its shared URL, or private "
            "again, and sets or removes the password that visitors must enter. "
            "Changing `public` removes any previously set password."
        ),
        request=UpdateDashboardSharingSerializer,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdateDashboardSharingSerializer, return_validated=True)
    def patch(
        self, request: Request, dashboard_id: int, data: Dict[str, Any]
    ) -> Response:
        """Updates the public sharing state of a dashboard."""

        dashboard = action_type_registry.get_by_type(
            UpdateDashboardSharingActionType
        ).do(request.user, dashboard_id, **data)
        return Response(PolymorphicApplicationResponseSerializer(dashboard).data)
