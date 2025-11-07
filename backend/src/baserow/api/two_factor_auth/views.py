from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.schemas import get_error_schema
from baserow.api.two_factor_auth.errors import (
    ERROR_RATE_LIMIT_EXCEEDED,
    ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED,
    ERROR_TWO_FACTOR_AUTH_CANNOT_BE_CONFIGURED,
    ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED,
    ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
    ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED,
    ERROR_WRONG_PASSWORD,
)
from baserow.api.two_factor_auth.serializers import (
    CreateTwoFactorAuthSerializer,
    DisableTwoFactorAuthSerializer,
    TwoFactorAuthSerializer,
    VerifyTOTPSerializer,
)
from baserow.api.two_factor_auth.tokens import Require2faToken
from baserow.api.user.schemas import authenticated_user_response_schema
from baserow.api.user.serializers import log_in_user
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.core.models import User
from baserow.core.two_factor_auth.actions import (
    ConfigureTwoFactorAuthActionType,
    DisableTwoFactorAuthActionType,
)
from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthAlreadyConfigured,
    TwoFactorAuthCannotBeConfigured,
    TwoFactorAuthNotConfigured,
    TwoFactorAuthTypeDoesNotExist,
    VerificationFailed,
    WrongPassword,
)
from baserow.core.two_factor_auth.handler import TwoFactorAuthHandler
from baserow.core.two_factor_auth.registries import (
    TOTPAuthProviderType,
    two_factor_auth_type_registry,
)
from baserow.throttling import RateLimitExceededException, rate_limit
from baserow.throttling_types import RateLimit


class ConfigureTwoFactorAuthView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        operation_id="configure_two_factor_auth",
        description=(
            "Configures two-factor authentication for the authenticated user."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            two_factor_auth_type_registry, CreateTwoFactorAuthSerializer
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                two_factor_auth_type_registry, TwoFactorAuthSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED"]),
            404: get_error_schema(["ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TwoFactorAuthTypeDoesNotExist: ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
            VerificationFailed: ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED,
            TwoFactorAuthAlreadyConfigured: ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED,
            TwoFactorAuthCannotBeConfigured: ERROR_TWO_FACTOR_AUTH_CANNOT_BE_CONFIGURED,
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
        provider = ConfigureTwoFactorAuthActionType.do(
            request.user, provider_type, **data
        )

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
            200: DiscriminatorCustomFieldsMappingSerializer(
                two_factor_auth_type_registry, TwoFactorAuthSerializer
            ),
        },
    )
    @transaction.atomic
    def get(self, request):
        """
        Returns two-factor configuration for the authenticated user.
        """

        provider = TwoFactorAuthHandler().get_provider(request.user)
        if provider is None:
            return Response(
                {"allowed": request.user.password != ""},  # nosec
                status=200,
            )

        serializer = two_factor_auth_type_registry.get_serializer(
            provider, TwoFactorAuthSerializer
        )
        return Response(serializer.data)


class DisableTwoFactorAuthView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        operation_id="disable_two_factor_auth",
        description=("Disables two-factor authentication for the authenticated user."),
        request=DisableTwoFactorAuthSerializer,
        responses={
            204: None,
            403: get_error_schema(["ERROR_WRONG_PASSWORD"]),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            WrongPassword: ERROR_WRONG_PASSWORD,
            TwoFactorAuthNotConfigured: ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED,
        }
    )
    @validate_body(DisableTwoFactorAuthSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data: dict):
        """
        Disables two-factor authentication for the authenticated user.
        """

        DisableTwoFactorAuthActionType.do(request.user, data.get("password"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyTOTPAuthView(APIView):
    permission_classes = (Require2faToken,)

    @extend_schema(
        tags=["Auth"],
        operation_id="verify_totp_auth",
        description=("Verifies TOTP two-factor authentication"),
        request=VerifyTOTPSerializer,
        responses={
            200: authenticated_user_response_schema,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(["ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED"]),
            404: get_error_schema(["ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"]),
            429: get_error_schema(["ERROR_RATE_LIMIT_EXCEEDED"]),
        },
    )
    @map_exceptions(
        {
            TwoFactorAuthTypeDoesNotExist: ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
            VerificationFailed: ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED,
            RateLimitExceededException: ERROR_RATE_LIMIT_EXCEEDED,
        }
    )
    @validate_body(VerifyTOTPSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data: dict):
        """
        Verifies TOTP two-factor authentication.
        """

        def verify():
            TwoFactorAuthHandler().verify(TOTPAuthProviderType.type, **data)

        rate_limit(
            rate=RateLimit.from_string("10/m"),
            key=f"two_fa_verify:totp:{data.get('email', '')}",
            raise_exception=True,
        )(verify)()

        user = User.objects.filter(email=data["email"]).first()
        return_data = log_in_user(request, user)

        return Response(
            return_data,
            status=status.HTTP_200_OK,
        )
