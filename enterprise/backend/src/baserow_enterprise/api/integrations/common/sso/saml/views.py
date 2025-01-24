from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.exceptions import (
    QueryParameterValidationException,
    RequestBodyValidationException,
)
from baserow.api.user_sources.errors import ERROR_USER_SOURCE_DOES_NOT_EXIST
from baserow.api.utils import validate_data
from baserow.core.user.exceptions import DeactivatedUserException
from baserow.core.user_sources.exceptions import (
    UserSourceDoesNotExist,
    UserSourceImproperlyConfigured,
)
from baserow.core.user_sources.handler import UserSourceHandler
from baserow_enterprise.api.integrations.common.sso.saml.serializers import (
    CommonSAMLResponseSerializer,
    CommonSsoLoginRequestSerializer,
)
from baserow_enterprise.api.sso.serializers import BaseSsoLoginRequestSerializer
from baserow_enterprise.api.sso.utils import (
    SsoErrorCode,
    get_valid_frontend_url,
    map_sso_exceptions,
    urlencode_query_params,
)
from baserow_enterprise.integrations.common.sso.saml.handler import (
    SamlAppAuthProviderHandler,
)
from baserow_enterprise.integrations.common.sso.saml.models import (
    SamlAppAuthProviderModel,
)
from baserow_enterprise.sso.saml.exceptions import (
    InvalidSamlConfiguration,
    InvalidSamlRequest,
    InvalidSamlResponse,
)


class SamlAppAuthProviderAssertionConsumerServiceView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Auth"],
        request=CommonSAMLResponseSerializer,
        operation_id="auth_provider_saml_acs_url",
        description=(
            "Complete the SAML authentication flow by validating the SAML response. "
            "Sign in the user if already exists in user_source or create a new one "
            "otherwise."
            "Once authenticated, the user will be redirected to the original "
            "URL they were trying to access. If the response is invalid, the user "
            "will be redirected to an error page with a specific error message."
            "It accepts the language code and the workspace invitation token as query "
            "parameters if provided."
        ),
        responses={302: None},
        auth=[],
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    def post(
        self,
        request: Request,
        user_source_uid,
    ) -> HttpResponseRedirect:
        user_source = UserSourceHandler().get_user_source_by_uid(user_source_uid)

        default_frontend_urls = (
            user_source.application.get_type().get_default_application_urls(
                user_source.application.specific
            )
        )

        error_raised = {"code": None}

        def on_error(error_code):
            error_raised["code"] = error_code

        with map_sso_exceptions(
            {
                InvalidSamlConfiguration: SsoErrorCode.INVALID_SAML_RESPONSE,
                InvalidSamlResponse: SsoErrorCode.INVALID_SAML_RESPONSE,
                DeactivatedUserException: SsoErrorCode.USER_DEACTIVATED,
                RequestBodyValidationException: SsoErrorCode.INVALID_SAML_RESPONSE,
                UserSourceDoesNotExist: SsoErrorCode.INVALID_SAML_REQUEST,
                UserSourceImproperlyConfigured: SsoErrorCode.INVALID_SAML_REQUEST,
            },
            on_error=on_error,
        ):
            # We can't use the decorator here because the redirect_url is related
            # to the user source and we don't have it before.
            data = validate_data(
                CommonSAMLResponseSerializer,
                request.data,
                return_validated=True,
            )

            next_path = data["saml_request_data"].pop("next", None)

            user = SamlAppAuthProviderHandler.sign_in_user_from_saml_response(
                data["SAMLResponse"],
                data["saml_request_data"],
                base_queryset=SamlAppAuthProviderModel.objects.filter(
                    user_source=user_source
                ),
            )

        if error_raised["code"]:
            # We redirect to the default frontend url with an error code
            error_url = urlencode_query_params(
                default_frontend_urls[0],
                {f"saml_error__{user_source.id}": error_raised["code"].value},
            )
            return redirect(error_url)

        query_params = {
            f"user_source_saml_token__{user_source.id}": user.get_refresh_token()
        }

        if next_path:
            query_params["next"] = next_path

        # Otherwise it a success, we redirect to the login page
        redirect_url = get_valid_frontend_url(
            data["RelayState"],
            default_frontend_urls=default_frontend_urls,
            # Add the refresh token as query parameter
            query_params=query_params,
            allow_any_path=False,
        )

        return redirect(redirect_url)


class SamlAppAuthProviderBaserowInitiatedSingleSignOn(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="email",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The email address of the user that want to sign in using SAML.",
            ),
            OpenApiParameter(
                name="original",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "The url to which the user should be redirected after a successful "
                    "login or sign up."
                ),
            ),
        ],
        tags=["User sources"],
        request=BaseSsoLoginRequestSerializer,
        operation_id="app_auth_provider_saml_sp_login",
        description=(
            "This is the endpoint that is called when the user wants to initiate a "
            "SSO SAML login from Baserow (the service provider). The user will be "
            "redirected to the SAML identity provider (IdP) where the user "
            "can authenticate. "
            "Once logged in in the IdP, the user will be redirected back "
            "to the assertion consumer service endpoint (ACS) where the SAML response "
            "will be validated and a new JWT session token will be provided to work "
            "with Baserow APIs."
        ),
        responses={302: None},
        auth=[],
    )
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, user_source_uid: str) -> HttpResponseRedirect:
        user_source = UserSourceHandler().get_user_source_by_uid(user_source_uid)

        default_frontend_urls = (
            user_source.application.get_type().get_default_application_urls(
                user_source.application.specific
            )
        )

        error_raised = {"code": None}

        def on_error(error_code):
            error_raised["code"] = error_code

        with map_sso_exceptions(
            {
                InvalidSamlConfiguration: SsoErrorCode.INVALID_SAML_REQUEST,
                InvalidSamlRequest: SsoErrorCode.INVALID_SAML_REQUEST,
                RequestBodyValidationException: SsoErrorCode.INVALID_SAML_REQUEST,
            },
            on_error=on_error,
        ):
            # Validate query parameters
            query_params = validate_data(
                CommonSsoLoginRequestSerializer,
                request.GET.dict(),
                partial=False,
                exception_to_raise=QueryParameterValidationException,
                return_validated=True,
            )

            original_url = query_params.pop("original", "")
            valid_relay_state_url = get_valid_frontend_url(
                original_url,
                query_params,
                default_frontend_urls=default_frontend_urls,
                allow_any_path=False,
            )

            idp_sign_in_url = SamlAppAuthProviderHandler.get_sign_in_url(
                query_params,
                SamlAppAuthProviderHandler.model_class.objects.filter(
                    user_source__uid=user_source.uid
                ),
                redirect_to=valid_relay_state_url,
            )

        if error_raised["code"]:
            # We redirect to the default frontend url with an error code
            error_url = urlencode_query_params(
                default_frontend_urls[0],
                {f"saml_error__{user_source.id}": error_raised["code"].value},
            )
            return redirect(error_url)

        return redirect(idp_sign_in_url)
