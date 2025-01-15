from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from baserow_premium.license.handler import CoreHandler
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
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.auth_provider.exceptions import AuthProviderModelNotFound
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.user.exceptions import DeactivatedUserException
from baserow.core.user_sources.exceptions import (
    UserSourceDoesNotExist,
    UserSourceImproperlyConfigured,
)
from baserow.core.user_sources.handler import UserSourceHandler
from baserow_enterprise.api.sso.serializers import BaseSsoLoginRequestSerializer
from baserow_enterprise.api.sso.utils import (
    SsoErrorCode,
    get_valid_frontend_url,
    map_sso_exceptions,
    urlencode_query_params,
)
from baserow_enterprise.integrations.common.sso.oauth2.app_auth_provider_types import (
    OpenIdConnectAppAuthProviderType,
)
from baserow_enterprise.sso.saml.exceptions import (
    InvalidSamlConfiguration,
    InvalidSamlResponse,
)


class OAuth2LoginView(APIView):
    permission_classes = (AllowAny,)

    AUTH_PROVIDER_TYPE = OpenIdConnectAppAuthProviderType

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="provider_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the provider for redirect.",
            ),
            OpenApiParameter(
                name="original",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The relative part of URL that the user wanted to access.",
            ),
            OpenApiParameter(
                name="workspace_invitation_token",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The invitation token sent to the "
                "user to join a specific workspace.",
            ),
        ],
        tags=["Auth"],
        operation_id="oauth_provider_login_redirect",
        description=(
            "Redirects to the OAuth2 provider's authentication URL "
            "based on the provided auth provider's id."
        ),
        responses={
            302: None,
        },
        auth=[],
    )
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def get(
        self, request: Request, user_source_uid: str, provider_type_name: str
    ) -> HttpResponseRedirect:
        """
        Redirects users to the authorization URL of the chosen provider
        to start OAuth2 login flow.
        """

        user_source = UserSourceHandler().get_user_source_by_uid(user_source_uid)
        application_urls = user_source.application.get_type().get_application_urls(
            user_source.application.specific
        )

        error_raised = {"code": None}

        def on_error(error_code):
            error_raised["code"] = error_code

        with map_sso_exceptions(
            {
                AuthProviderModelNotFound: SsoErrorCode.PROVIDER_DOES_NOT_EXIST,
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

            # original_url = query_params.pop("original", application_urls[0])

            # provider = AuthProviderHandler.get_auth_provider_by_id(provider_id)

            provider_type = app_auth_provider_type_registry.get(provider_type_name)
            provider = provider_type.model_class.objects.get(
                user_source_id=user_source.id
            )

            # TODO use client_id to get the right provider

            redirect_url = provider_type.get_authorization_url(
                # TODO they are potentially many of them. Use django session
                # to store client id?
                provider,
                session=request.session,
                query_params=query_params,
            )

            return redirect(redirect_url)

        # We redirect to the default frontend url with an error code as an error
        # happened
        error_url = urlencode_query_params(
            application_urls[0],
            {f"oidc_error__{user_source.id}": error_raised["code"].value},
        )
        return redirect(error_url)


class OAuth2CallbackView(APIView):
    permission_classes = (AllowAny,)

    AUTH_PROVIDER_TYPE = OpenIdConnectAppAuthProviderType

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="provider_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the provider for which to process the callback.",
            ),
            OpenApiParameter(
                name="code",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The id of the provider for which to process the callback.",
            ),
        ],
        tags=["Auth"],
        operation_id="oauth_provider_login_callback",
        description=(
            "Processes callback from OAuth2 provider and "
            "logs the user in if successful."
        ),
        responses={
            302: None,
        },
        auth=[],
    )
    @transaction.atomic
    def get(
        self, request: Request, user_source_uid: str, provider_type_name: str
    ) -> HttpResponseRedirect:
        """
        Processes callback from OAuth2 authentication provider by
        using the 'code' parameter to obtain tokens and query for user
        details. If successful, the user is given JWT token and is logged
        in.
        """

        user_source = UserSourceHandler().get_user_source_by_uid(user_source_uid)
        application_urls = user_source.application.get_type().get_application_urls(
            user_source.application.specific
        )

        user = None
        application_urls = None
        error_raised = {"code": None}

        def on_error(error_code):
            error_raised["code"] = error_code

        # We can't use the view decorator here because the redirect_url is related
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
            provider_type = app_auth_provider_type_registry.get(provider_type_name)
            provider = provider_type.model_class.objects.get(user_source=user_source)

            print(request.query_params)

            code = request.query_params.get("code", None)

            user_info, original_url = provider_type.get_user_info(
                provider, code, request.session
            )

            application = CoreHandler().get_application_for_url(original_url)
            if application is None:
                raise ApplicationDoesNotExist()
            application_urls = application.get_type().get_application_urls(
                application.specific
            )

            (
                user,
                _,
            ) = provider_type.get_or_create_user_and_sign_in(provider, user_info)

            # TODO? next?
            query_params = {}
            query_params[
                f"user_source_oidc_token__{user.user_source.id}"
            ] = user.get_refresh_token()

            # Otherwise it's a success, we redirect to the login page
            redirect_url = get_valid_frontend_url(
                original_url,
                default_frontend_urls=application_urls,
                query_params=query_params,
                allow_any_path=False,
            )

            return redirect(redirect_url)

        # If we are here it means that an error was raised so error_raised["code"] is
        # not empty
        if not application_urls or not user:
            raise Exception(f"Broken {error_raised['code']}")

        # We redirect to the default frontend url with an error code
        error_url = urlencode_query_params(
            application_urls[0],
            {f"oidc_error__{user.user_source.id}": error_raised["code"].value},
        )
        return redirect(error_url)
