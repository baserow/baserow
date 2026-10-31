from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.mixins import RealtimeRecoveryPrimaryReadMixin
from baserow.api.schemas import get_error_schema
from baserow.api.settings.registries import settings_data_registry
from baserow.core.handler import CoreHandler
from baserow.core.user_templates.handler import UserTemplateHandler

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
            "Updates the admin configured settings if the user has admin "
            "permissions. Switching `user_templates_require_approval` from true "
            "to false approves every user template in review."
        ),
        request=SettingsSerializer,
        responses={
            200: SettingsSerializer,
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
        },
    )
    @map_exceptions()
    @validate_body(SettingsSerializer, partial=True, return_validated=True)
    @transaction.atomic
    def patch(self, request, data):
        """
        Updates the provided config settings if the user has admin permissions.
        """

        # Only switching approval off approves the templates in review: sending
        # false again keeps one that waits with approval off, like a rejected one
        # made public again. Not from the cache, which can be stale.
        switches_off = data.get(
            "user_templates_require_approval"
        ) is False and UserTemplateHandler().read_require_approval(for_update=True)
        settings = CoreHandler().update_settings(request.user, **data)
        if switches_off:
            UserTemplateHandler().approve_waiting_revisions(request.user)
        return Response(SettingsSerializer(settings).data)
