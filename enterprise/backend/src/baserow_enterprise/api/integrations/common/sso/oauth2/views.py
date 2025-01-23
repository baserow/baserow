from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from baserow.api.auth_provider.errors import ERROR_AUTH_PROVIDER_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions
from baserow.api.exceptions import QueryParameterValidationException
from baserow.api.user_sources.errors import ERROR_USER_SOURCE_DOES_NOT_EXIST
from baserow.api.utils import validate_data
from baserow.core.app_auth_providers.handler import AppAuthProviderHandler
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.auth_provider.exceptions import (
    AuthProviderModelNotFound,
    DifferentAuthProvider,
)
from baserow.core.user.exceptions import DeactivatedUserException
from baserow.core.user_sources.exceptions import UserSourceDoesNotExist
from baserow.core.user_sources.handler import UserSourceHandler
from baserow_enterprise.api.integrations.common.sso.oauth2.serializers import (
    OIDCLoginRequestSerializer,
)
from baserow_enterprise.api.sso.utils import (
    SsoErrorCode,
    get_valid_frontend_url,
    map_sso_exceptions,
    urlencode_query_params,
)
from baserow_enterprise.integrations.common.sso.oauth2.app_auth_provider_types import (
    OpenIdConnectAppAuthProviderType,
)
from baserow_enterprise.sso.exceptions import AuthFlowError


class OAuth2LoginView(APIView):
    permission_classes = (AllowAny,)

    AUTH_PROVIDER_TYPE = OpenIdConnectAppAuthProviderType

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_uid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The uid of the user source to use for authentication.",
            ),
            OpenApiParameter(
                name="original",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The URL that the user wants to access.",
            ),
            OpenApiParameter(
                name="iss",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The issuer of the authentication.",
            ),
        ],
        tags=["User sources"],
        operation_id="app_auth_oidc_login_redirect",
        description=(
            "Redirects to the OAuth2 provider's authentication URL "
            "based on the provided user source uid and issuer."
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
        Redirects users to the authorization URL of the chosen user source / provider
        to start OAuth2 login flow.
        """

        user_source = UserSourceHandler().get_user_source_by_uid(
            user_source_uid=user_source_uid
        )

        application = user_source.application.specific
        application_urls = application.get_type().get_application_urls(application)

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
                OIDCLoginRequestSerializer,
                request.GET.dict(),
                partial=False,
                exception_to_raise=QueryParameterValidationException,
                return_validated=True,
            )

            issuer = query_params["iss"]
            provider_type = app_auth_provider_type_registry.get(provider_type_name)

            provider = provider_type.model_class.objects.filter(
                user_source=user_source, base_url=issuer
            ).first()

            # Save provider id for callback
            request.session["oauth_2_provider_id"] = provider.id

            redirect_url = provider.get_type().get_authorization_url(
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
                name="user_source_uid",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The uid of the user source for which to process the "
                "callback.",
            ),
            OpenApiParameter(
                name="code",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The code returned by the IDP.",
            ),
            OpenApiParameter(
                name="state",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The oauth state returned by the IDP.",
            ),
        ],
        tags=["User sources"],
        operation_id="app_auth_oidc_login_callback",
        description=(
            "Processes callback from OAuth2 provider and "
            "logs the user in if successful."
        ),
        responses={
            302: None,
        },
        auth=[],
    )
    @map_exceptions(
        {
            AuthProviderModelNotFound: ERROR_AUTH_PROVIDER_DOES_NOT_EXIST,
        }
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

        auth_provider_id = request.session.pop("oauth_2_provider_id", None)
        if not auth_provider_id:
            raise AuthProviderModelNotFound("Missing auth provider id.")

        provider = AppAuthProviderHandler().get_auth_provider_by_id(auth_provider_id)

        if (
            # The provider_type_name check is not necessary but I want to keep it
            # for now if we need it later as we don't want to force the user to
            # change their IDP configuration as much as possible.
            # Same for user_source_uid.
            provider_type_name != provider.get_type().type
            or provider.user_source.uid != user_source_uid
        ):
            raise AuthProviderModelNotFound()

        application = provider.user_source.application.specific
        application_urls = application.get_type().get_application_urls(application)

        user = None
        error_raised = {"code": None}

        def on_error(error_code):
            error_raised["code"] = error_code

        # We can't use the view decorator here because the redirect_url is related
        # to the application and we don't have it before.
        with map_sso_exceptions(
            {
                AuthFlowError: SsoErrorCode.AUTH_FLOW_ERROR,
                DeactivatedUserException: SsoErrorCode.USER_DEACTIVATED,
                DifferentAuthProvider: SsoErrorCode.DIFFERENT_PROVIDER,
            },
            on_error=on_error,
        ):
            code = request.query_params.get("code", None)

            user_info, original_url = provider.get_type().get_user_info(
                provider, code, request.session
            )

            (
                user,
                _,
            ) = provider.get_type().get_or_create_user_and_sign_in(provider, user_info)

            # Adds the refresh token to the query params of redirect URL
            query_params = {
                f"user_source_oidc_token__{user.user_source.id}": user.get_refresh_token()
            }

            # Otherwise it's a success, we redirect to the login page
            redirect_url = get_valid_frontend_url(
                original_url,
                default_frontend_urls=application_urls,
                query_params=query_params,
                allow_any_path=False,
            )

            return redirect(redirect_url)

        # We redirect to the default frontend url with an error code
        error_url = urlencode_query_params(
            application_urls[0],
            {f"oidc_error__{provider.user_source.id}": error_raised["code"].value},
        )
        return redirect(error_url)
