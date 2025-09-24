from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from baserow.core.two_factor_auth.registries import two_factor_auth_type_registry
from baserow.api.decorators import map_exceptions, validate_body_custom_fields
from baserow.api.schemas import get_error_schema
from baserow.api.two_factor_auth.errors import ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST
from baserow.api.two_factor_auth.serializers import (
    CreateTwoFactorAuthSerializer,
    TwoFactorAuthSerializer,
)
from baserow.core.two_factor_auth.actions import ConfigureTwoFactorAuthActionType
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthTypeDoesNotExist
from drf_spectacular.utils import extend_schema


class ConfigureTwoFactorAuthView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        operation_id="setup_two_factor_auth",
        description=(
            "Configures two-factor authentication for the authenticated user."
        ),
        request=TwoFactorAuthSerializer,  # FIXME:
        responses={
            200: TwoFactorAuthSerializer,  # FIXME:
            400: get_error_schema([]),
            404: get_error_schema(["ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TwoFactorAuthTypeDoesNotExist: ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_body_custom_fields(
        two_factor_auth_type_registry,
        base_serializer_class=CreateTwoFactorAuthSerializer,
    )
    @transaction.atomic
    def post(self, request, data: dict):
        """
        Configures two-factor authentication for the authenticated user.
        """

        provider_type = data.pop("type")
        provider = ConfigureTwoFactorAuthActionType.do(request.user, provider_type)

        serializer = two_factor_auth_type_registry.get_serializer(
            provider, TwoFactorAuthSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        tags=["Auth"],
        operation_id="two_factor_auth_configuration",
        description=(
            "Returns two-factor auth configuration for the authenticated user."
        ),
        request=None,
        responses={
            200: TwoFactorAuthSerializer,
        },
    )
    @transaction.atomic
    def get(self, request):
        """
        Returns two-factor configuration for the authenticated user.
        """

        pass
