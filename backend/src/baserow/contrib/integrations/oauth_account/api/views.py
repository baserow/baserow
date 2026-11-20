from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.api.schemas import get_error_schema
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
)
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.registries import integration_type_registry

from ..actions import ConnectOAuthAccountActionType, DisconnectOAuthAccountActionType
from ..exceptions import (
    AccountMismatch,
    AdminConsentRequired,
    ClientRejected,
    OAuthAccountNotConfigured,
    OAuthAccountTypeDoesNotExist,
    OAuthFailed,
    OAuthStateInvalid,
    ServiceTypeNotAllowed,
    SignInCancelled,
    TenantNotAllowed,
)
from ..handler import OAuthAccountHandler
from ..service import OAuthAccountService, get_oauth_account_integration_type
from .errors import (
    ERROR_OAUTH_ACCOUNT_MISMATCH,
    ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST,
    ERROR_OAUTH_ADMIN_CONSENT_REQUIRED,
    ERROR_OAUTH_CLIENT_REJECTED,
    ERROR_OAUTH_FAILED,
    ERROR_OAUTH_NOT_CONFIGURED,
    ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED,
    ERROR_OAUTH_SIGN_IN_CANCELLED,
    ERROR_OAUTH_STATE_INVALID,
    ERROR_OAUTH_TENANT_NOT_ALLOWED,
)
from .serializers import (
    OAuthAccountCompleteResponseSerializer,
    OAuthAccountCompleteSerializer,
    OAuthAccountConfigSerializer,
    OAuthAccountStartResponseSerializer,
    OAuthAccountStartSerializer,
)
from .throttling import OAuthAccountStartRateThrottle

INTEGRATION_TYPE_PARAMETER = OpenApiParameter(
    name="integration_type",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.STR,
    description="The integration type that connects an account, e.g. `microsoft`.",
)
INTEGRATION_ID_PARAMETER = OpenApiParameter(
    name="integration_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the integration.",
)

EXCEPTIONS = {
    ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
    IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
    OAuthAccountTypeDoesNotExist: ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST,
    OAuthAccountNotConfigured: ERROR_OAUTH_NOT_CONFIGURED,
    OAuthStateInvalid: ERROR_OAUTH_STATE_INVALID,
    OAuthFailed: ERROR_OAUTH_FAILED,
    SignInCancelled: ERROR_OAUTH_SIGN_IN_CANCELLED,
    AdminConsentRequired: ERROR_OAUTH_ADMIN_CONSENT_REQUIRED,
    TenantNotAllowed: ERROR_OAUTH_TENANT_NOT_ALLOWED,
    ClientRejected: ERROR_OAUTH_CLIENT_REJECTED,
    AccountMismatch: ERROR_OAUTH_ACCOUNT_MISMATCH,
    ServiceTypeNotAllowed: ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED,
}


def _serialize(integration) -> dict:
    return integration_type_registry.get_serializer(
        integration, IntegrationSerializer
    ).data


class OAuthAccountConfigView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_TYPE_PARAMETER],
        tags=["Integrations"],
        operation_id="get_oauth_account_config",
        description=(
            "Whether this installation can connect accounts of the provider of "
            "an integration type, and the redirect URI its OAuth client must "
            "have."
        ),
        responses={
            200: OAuthAccountConfigSerializer,
            404: get_error_schema(["ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    def get(self, request, integration_type: str):
        handler = OAuthAccountHandler(
            get_oauth_account_integration_type(integration_type)
        )
        provider = handler.provider
        return Response(
            {
                "configured": provider.is_configured(),
                "redirect_uri": handler.redirect_uri,
                "allow_account_switch": provider.allow_account_switch,
                "keep_connection_in_published_copies": (
                    provider.keep_connection_in_published_copies
                ),
            }
        )


class OAuthAccountStartView(APIView):
    throttle_classes = (*APIView.throttle_classes, OAuthAccountStartRateThrottle)

    @extend_schema(
        parameters=[INTEGRATION_TYPE_PARAMETER],
        tags=["Integrations"],
        operation_id="start_oauth_account_sign_in",
        description=(
            "Starts signing in to a provider, to create an integration of this "
            "type in an application or to connect one again. Open the returned "
            "URL in a popup: the provider redirects back to a Baserow page, which "
            "finishes the sign-in with the complete endpoint."
        ),
        request=OAuthAccountStartSerializer,
        responses={
            200: OAuthAccountStartResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_OAUTH_NOT_CONFIGURED",
                    "ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED",
                    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST",
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_INTEGRATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(OAuthAccountStartSerializer, return_validated=True)
    def post(self, request, data: dict, integration_type: str):
        service = OAuthAccountService(
            get_oauth_account_integration_type(integration_type)
        )
        url = service.start_sign_in(
            request.user,
            data["service_types"],
            application_id=data["application_id"],
            integration_id=data["integration_id"],
            name=data["name"],
        )
        return Response({"authorization_url": url})


class OAuthAccountCompleteView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_TYPE_PARAMETER],
        tags=["Integrations"],
        operation_id="complete_oauth_account_sign_in",
        description=(
            "Finishes signing in to a provider with what it redirected back with. "
            "Only the user who started the sign-in can finish it. With "
            "`ERROR_OAUTH_ADMIN_CONSENT_REQUIRED`, the detail is the URL where an "
            "admin of the organisation approves Baserow, when the provider has "
            "one."
        ),
        request=OAuthAccountCompleteSerializer,
        responses={
            200: OAuthAccountCompleteResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_OAUTH_NOT_CONFIGURED",
                    "ERROR_OAUTH_STATE_INVALID",
                    "ERROR_OAUTH_FAILED",
                    "ERROR_OAUTH_SIGN_IN_CANCELLED",
                    "ERROR_OAUTH_ADMIN_CONSENT_REQUIRED",
                    "ERROR_OAUTH_TENANT_NOT_ALLOWED",
                    "ERROR_OAUTH_CLIENT_REJECTED",
                    "ERROR_OAUTH_ACCOUNT_MISMATCH",
                    "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST",
                    "ERROR_APPLICATION_DOES_NOT_EXIST",
                    "ERROR_INTEGRATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(OAuthAccountCompleteSerializer, return_validated=True)
    def post(self, request, data: dict, integration_type: str):
        completed = ConnectOAuthAccountActionType.do(
            request.user,
            get_oauth_account_integration_type(integration_type),
            data["state"],
            data["code"],
            data["error"],
            data["error_description"],
        )
        return Response(
            {
                "created": completed.created,
                "integration": _serialize(completed.integration),
            }
        )


class OAuthAccountDisconnectView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_TYPE_PARAMETER, INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="disconnect_oauth_account",
        description=(
            "Forgets the tokens of an integration that connects an account. "
            "Published applications and workflows keep their copy until they're "
            "published again."
        ),
        request=None,
        responses={
            200: IntegrationSerializer,
            404: get_error_schema(
                [
                    "ERROR_OAUTH_ACCOUNT_TYPE_DOES_NOT_EXIST",
                    "ERROR_INTEGRATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(EXCEPTIONS)
    def post(self, request, integration_type: str, integration_id: int):
        integration = DisconnectOAuthAccountActionType.do(
            request.user,
            get_oauth_account_integration_type(integration_type),
            integration_id,
        )
        return Response(_serialize(integration))
