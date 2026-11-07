from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_DATABASE_DEADLOCK
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.schemas import get_error_schema
from baserow.api.settings.registries import settings_data_registry
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import UpdateAdminSettingsActionType
from baserow.core.db import atomic_with_retry_on_deadlock
from baserow.core.exceptions import DeadlockException
from baserow.core.feature_flags import FF_USER_TEMPLATES, feature_flag_is_enabled
from baserow.core.handler import CoreHandler

from .serializers import InstanceIdSerializer, SettingsSerializer


class SettingsView(RealtimeRecoveryPrimaryReadMixin, APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Settings"],
        operation_id="get_settings",
        description="Responds with all the admin configured settings.",
        responses={
            200: SettingsSerializer,
        },
        auth=[],
    )
    def get(self, request):
        """Responds with all the admin configured settings."""

        settings = CoreHandler().get_settings()
        data = SettingsSerializer(settings).data
        data.update(**settings_data_registry.get_all_settings_data(request))
        return Response(data)


class InstanceIdView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Settings"],
        operation_id="get_instance_id",
        description="Responds with the self hosted instance id. Only a user with "
        "staff permissions can request it.",
        responses={
            200: InstanceIdSerializer,
        },
    )
    def get(self, request):
        """Responds with the instance id."""

        settings = CoreHandler().get_settings()
        return Response(InstanceIdSerializer(settings).data)


class UpdateSettingsView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Settings"],
        operation_id="update_settings",
        description=(
            "Updates the admin configured settings if the user has admin permissions."
        ),
        request=SettingsSerializer,
        responses={
            200: SettingsSerializer,
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            409: get_error_schema(["ERROR_DATABASE_DEADLOCK"]),
        },
    )
    @map_exceptions({DeadlockException: ERROR_DATABASE_DEADLOCK})
    @validate_body(SettingsSerializer, partial=True, return_validated=True)
    # Switching approval off approves the pending templates, which can deadlock
    # with a user deletion: Postgres cancels one side, so it's tried again.
    @atomic_with_retry_on_deadlock()
    def patch(self, request, data):
        """
        Updates the provided config settings if the user has admin permissions.
        """

        if "user_templates_require_approval" in data:
            feature_flag_is_enabled(FF_USER_TEMPLATES, raise_if_disabled=True)
        settings = action_type_registry.get_by_type(UpdateAdminSettingsActionType).do(
            request.user, **data
        )
        return Response(SettingsSerializer(settings).data)
