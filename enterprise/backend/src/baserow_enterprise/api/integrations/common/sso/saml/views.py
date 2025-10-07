from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions
from baserow.api.exceptions import (
    QueryParameterValidationException,
    RequestBodyValidationException,
)
from baserow.api.user_sources.errors import ERROR_USER_SOURCE_DOES_NOT_EXIST
from baserow.api.utils import validate_data
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.user.exceptions import DeactivatedUserException
from baserow.core.user_sources.exceptions import (
    UserSourceDoesNotExist,
    UserSourceImproperlyConfigured,
)
from baserow.core.user_sources.handler import UserSourceHandler
from baserow_enterprise.api.integrations.common.sso.saml.serializers import (
    CommonSAMLResponseSerializer,
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
        tags=["User sources"],
        request=CommonSAMLResponseSerializer,
        operation_id="auth_provider_saml_acs_url",
        description=(
            "Complete the SAML authentication flow by validating the SAML response. "
            "Sign in the user if already exists in the user source or create a new one "
            "otherwise."
            "Once authenticated, the user will be redirected to the original "
            "URL they were trying to access. If the response is invalid, the user "
            "will be redirected to an error page with a specific error message."
        ),
        responses={302: None},
        auth=[],
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            InvalidSamlRequest: SsoErrorCode.INVALID_SAML_REQUEST,
        }
    )
    def post(
        self,
        request: Request,
    ) -> HttpResponseRedirect:
        user = None
        application_urls = None
        error_raised = {"code": None}

        logger.debug("SAML ACS response payload: {0}", request.data)

        def on_error(error_code):
            error_raised["code"] = error_code

        # We can't use the decorator here because the redirect_url is related
        # to the application and we don't have it before.
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
            data = validate_data(
                CommonSAMLResponseSerializer,
                request.data,
                return_validated=True,
            )

            origin = data["RelayState"]

            application = CoreHandler().get_application_for_url(origin)
            if application is None:
                raise ApplicationDoesNotExist()
            application_urls = application.get_type().get_application_urls(
                application.specific
            )

            user = SamlAppAuthProviderHandler.sign_in_user_from_saml_response(
                data["SAMLResponse"],
                {},
                base_queryset=SamlAppAuthProviderModel.objects.filter(
                    user_source__application=application,
                ),
            )

            query_params = data.get("saml_request_data", {})
            # Add the refresh token as query parameter
            query_params[
                f"user_source_saml_token__{user.user_source.id}"
            ] = user.get_refresh_token()

            # Otherwise it's a success, we redirect to the login page
            redirect_url = get_valid_frontend_url(
                origin,
                default_frontend_urls=application_urls,
                query_params=query_params,
                allow_any_path=False,
            )

            return redirect(redirect_url)

        # If we are here it means that an error was raised so error_raised["code"] is
        # not empty
        if not application_urls or not user:
            raise InvalidSamlRequest(f"Something when wrong {error_raised['code']}")

        # We redirect to the default frontend url with an error code
        error_url = urlencode_query_params(
            application_urls[0],
            {f"saml_error__{user.user_source.id}": error_raised["code"].value},
        )
        return redirect(error_url)


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

        application_urls = user_source.application.get_type().get_application_urls(
            user_source.application.specific
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
                BaseSsoLoginRequestSerializer,
                request.GET.dict(),
                partial=False,
                exception_to_raise=QueryParameterValidationException,
                return_validated=True,
            )

            original_url = query_params.pop("original", application_urls[0])

            valid_relay_state_url = get_valid_frontend_url(
                original_url,
                query_params,
                default_frontend_urls=application_urls,
                allow_any_path=False,
            )

            idp_sign_in_url = SamlAppAuthProviderHandler.get_sign_in_url(
                query_params,
                SamlAppAuthProviderHandler.model_class.objects.filter(
                    user_source=user_source
                ),
                relay_state=valid_relay_state_url,
            )
            return redirect(idp_sign_in_url)

        # We redirect to the default frontend url with an error code as an error
        # happened
        error_url = urlencode_query_params(
            application_urls[0],
            {f"saml_error__{user_source.id}": error_raised["code"].value},
        )
        return redirect(error_url)
