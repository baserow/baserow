from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.schemas import get_error_schema
from baserow.contrib.integrations.oauth2.exceptions import (
    OAuth2IntegrationNotConfigured,
    OAuth2InvalidReturnUrl,
    OAuth2InvalidState,
    OAuth2TokenRequestFailed,
)
from baserow.contrib.integrations.oauth2.handler import OAuth2IntegrationHandler
from baserow.contrib.integrations.oauth2.integration_types import (
    OAuth2IntegrationTypeMixin,
)
from baserow.core.exceptions import PermissionException, UserNotInWorkspace
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler

from .errors import (
    ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED,
    ERROR_OAUTH2_INVALID_RETURN_URL,
    ERROR_OAUTH2_NOT_SUPPORTED,
)
from .serializers import (
    OAuth2AuthorizeRequestSerializer,
    OAuth2AuthorizeResponseSerializer,
)


class OAuth2NotSupported(Exception):
    """The integration type has no OAuth2 flow."""


class OAuth2AuthorizeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="integration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The integration to connect to an account.",
            ),
        ],
        tags=["Integrations"],
        operation_id="oauth2_authorize_integration",
        description=(
            "Starts connecting an OAuth2 integration (Google, Microsoft) to an "
            "account. Answers the provider's consent URL to send the browser to; "
            "the provider later calls back to Baserow, which stores the tokens "
            "and redirects to `return_url`."
        ),
        request=OAuth2AuthorizeRequestSerializer,
        responses={
            200: OAuth2AuthorizeResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED",
                    "ERROR_OAUTH2_INVALID_RETURN_URL",
                    "ERROR_OAUTH2_NOT_SUPPORTED",
                ]
            ),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            OAuth2IntegrationNotConfigured: ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED,
            OAuth2InvalidReturnUrl: ERROR_OAUTH2_INVALID_RETURN_URL,
            OAuth2NotSupported: ERROR_OAUTH2_NOT_SUPPORTED,
        }
    )
    @validate_body(OAuth2AuthorizeRequestSerializer, return_validated=True)
    def post(self, request, data, integration_id: int):
        integration = IntegrationHandler().get_integration(integration_id)
        if not isinstance(integration.get_type(), OAuth2IntegrationTypeMixin):
            raise OAuth2NotSupported()
        authorization_url = OAuth2IntegrationHandler().get_authorization_url(
            request.user, integration, data["return_url"]
        )
        return Response({"authorization_url": authorization_url})


class OAuth2CallbackView(APIView):
    # The provider's redirect carries no Baserow session; the signed state
    # names the user and integration and is what authorizes the request.
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="code",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The authorization code the provider issued.",
            ),
            OpenApiParameter(
                name="state",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The signed state Baserow put in the consent URL.",
            ),
            OpenApiParameter(
                name="error",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Set by the provider when consent was refused.",
            ),
        ],
        tags=["Integrations"],
        operation_id="oauth2_integration_callback",
        description=(
            "Where the provider sends the browser after the consent screen. "
            "Stores the account's tokens on the integration and redirects to "
            "the page the flow was started from, with `oauth2_status` set to "
            "`success` or `error` and `oauth2_error` describing a failure."
        ),
        responses={302: None},
    )
    @transaction.atomic
    def get(self, request):
        handler = OAuth2IntegrationHandler()
        state = request.GET.get("state")
        try:
            data = handler.parse_state(state)
        except OAuth2InvalidState:
            # No trusted page to return to, so the frontend root explains it.
            return HttpResponseRedirect(
                f"{settings.PUBLIC_WEB_FRONTEND_URL.rstrip('/')}/?"
                + urlencode(
                    {
                        "oauth2_status": "error",
                        "oauth2_error": "The connection request expired or was "
                        "tampered with. Start again from the integration.",
                    }
                )
            )
        return_url = data["return_url"]
        status = {"oauth2_integration": data["integration_id"]}
        provider_error = request.GET.get("error")
        code = request.GET.get("code")
        if provider_error or not code:
            status.update(
                oauth2_status="error",
                oauth2_error=request.GET.get("error_description")
                or provider_error
                or "The provider did not answer with a code.",
            )
        else:
            try:
                handler.complete_authorization(code, state)
                status["oauth2_status"] = "success"
            except (
                OAuth2InvalidState,
                OAuth2TokenRequestFailed,
                PermissionException,
                UserNotInWorkspace,
            ) as e:
                status.update(oauth2_status="error", oauth2_error=str(e))
        separator = "&" if "?" in return_url else "?"
        return HttpResponseRedirect(f"{return_url}{separator}{urlencode(status)}")
