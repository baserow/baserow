from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.api.two_factor_auth.errors import ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST
from baserow.api.two_factor_auth.serializers import TwoFactorAuthSerializer
from baserow.core.two_factor_auth.actions import ConfigureTwoFactorAuthActionType
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthTypeDoesNotExist
from drf_spectacular.utils import extend_schema


class TwoFactorAuthView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        operation_id="setup_two_factor_auth",
        description=(
            "Configures two-factor authentication for the authenticated user."
        ),
        request=TwoFactorAuthSerializer,
        responses={
            200: TwoFactorAuthSerializer,
            400: get_error_schema([]),
            404: get_error_schema(["ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TwoFactorAuthTypeDoesNotExist: ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request):
        """
        Configures two-factor authentication for the authenticated user.
        """

        ConfigureTwoFactorAuthActionType.do(request.user)

        serializer = TwoFactorAuthSerializer(request.data)
        serializer.is_valid(raise_exception=True)

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
