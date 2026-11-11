from typing import Any, Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
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
from baserow.contrib.dashboard.actions import UpdateDashboardSharingActionType
from baserow.contrib.dashboard.api.errors import ERROR_DASHBOARD_DOES_NOT_EXIST
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow_premium.api.views.errors import (
    ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE,
)
from baserow_premium.api.views.exceptions import (
    CannotUpdatePremiumAttributesOnTemplate,
)
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler

from .serializers import UpdatePremiumDashboardAttributesSerializer


class PremiumDashboardAttributesView(APIView):
    """
    Updates the dashboard attributes that only premium users may change, such as
    hiding the Baserow logo on the publicly shared dashboard. The generic
    application endpoint ignores these attributes.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the premium attributes of the dashboard "
                "related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard"],
        operation_id="premium_dashboard_attributes_update",
        description="Sets dashboard attributes only available for premium users.",
        request=UpdatePremiumDashboardAttributesSerializer,
        responses={
            200: PolymorphicApplicationResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE",
                ]
            ),
            402: get_error_schema(["ERROR_FEATURE_NOT_AVAILABLE"]),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            CannotUpdatePremiumAttributesOnTemplate: ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE,  # noqa: E501
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdatePremiumDashboardAttributesSerializer)
    def patch(
        self, request: Request, dashboard_id: int, data: Dict[str, Any]
    ) -> Response:
        """Sets dashboard attributes only available for premium users."""

        dashboard = DashboardHandler().get_dashboard_for_update(dashboard_id)
        workspace = dashboard.workspace
        if workspace.has_template():
            raise CannotUpdatePremiumAttributesOnTemplate()
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, request.user, workspace
        )

        dashboard = action_type_registry.get_by_type(
            UpdateDashboardSharingActionType
        ).do(request.user, dashboard.id, **data)
        return Response(PolymorphicApplicationResponseSerializer(dashboard).data)
