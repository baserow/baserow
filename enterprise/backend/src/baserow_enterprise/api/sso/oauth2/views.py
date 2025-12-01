from typing import Any, Dict

from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from baserow.api.decorators import validate_query_parameters
from baserow.core.auth_provider.exceptions import (
    AuthProviderModelNotFound,
    DifferentAuthProvider,
)
from baserow.core.auth_provider.handler import AuthProviderHandler
from baserow.core.exceptions import WorkspaceInvitationEmailMismatch
from baserow.core.user.exceptions import DeactivatedUserException, DisabledSignupError
from baserow_enterprise.api.sso.serializers import SsoLoginRequestSerializer
from baserow_enterprise.api.sso.utils import (
    SsoErrorCode,
    map_sso_exceptions,
    redirect_to_sign_in_error_page,
    redirect_user_on_success,
)
from baserow_enterprise.sso.exceptions import AuthFlowError
from baserow_enterprise.sso.utils import is_sso_feature_active


class OAuth2LoginView(APIView):
    permission_classes = (AllowAny,)

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
    @validate_query_parameters(SsoLoginRequestSerializer, return_validated=True)
    @map_sso_exceptions(
        {
            AuthProviderModelNotFound: SsoErrorCode.PROVIDER_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def get(
        self, request: Request, provider_id: int, query_params: Dict[str, Any]
    ) -> HttpResponseRedirect:
        """
        Redirects users to the authorization URL of the chosen provider
        to start OAuth2 login flow.
        """

        if not is_sso_feature_active():
            return redirect_to_sign_in_error_page(SsoErrorCode.FEATURE_NOT_ACTIVE)

        provider = AuthProviderHandler.get_auth_provider_by_id(provider_id)

        redirect_url = provider.get_type().get_authorization_url(
            provider.specific_class.objects.get(id=provider_id),
            session=request.session,
            query_params=query_params,
        )

        return redirect(redirect_url)


class OAuth2CallbackView(APIView):
    permission_classes = (AllowAny,)

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
                type=OpenApiTypes.STR,
                description="The code returned by the IDP.",
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
    @map_sso_exceptions(
        {
            AuthProviderModelNotFound: SsoErrorCode.PROVIDER_DOES_NOT_EXIST,
            AuthFlowError: SsoErrorCode.AUTH_FLOW_ERROR,
            DeactivatedUserException: SsoErrorCode.USER_DEACTIVATED,
            DifferentAuthProvider: SsoErrorCode.DIFFERENT_PROVIDER,
            WorkspaceInvitationEmailMismatch: SsoErrorCode.GROUP_INVITATION_EMAIL_MISMATCH,
            DisabledSignupError: SsoErrorCode.SIGNUP_DISABLED,
        }
    )
    @transaction.atomic
    def get(self, request: Request, provider_id: int) -> HttpResponseRedirect:
        """
        Processes callback from OAuth2 authentication provider by
        using the 'code' parameter to obtain tokens and query for user
        details. If successful, the user is given JWT token and is logged
        in.
        """

        if not is_sso_feature_active():
            return redirect_to_sign_in_error_page(SsoErrorCode.FEATURE_NOT_ACTIVE)

        provider = AuthProviderHandler.get_auth_provider_by_id(provider_id)

        logger.debug(
            "OAuth2 callback request GET query params: {0}", dict(request.query_params)
        )
        logger.debug("OAuth2 callback session data: {0}", request.session._session)

        code = request.query_params.get("code", None)
        user_info, original_url = provider.get_type().get_user_info(
            provider, code, request.session
        )
        logger.debug("OAuth2 extracted user info: {0}", user_info)

        (
            user,
            _,
        ) = provider.get_type().get_or_create_user_and_sign_in(provider, user_info)

        return redirect_user_on_success(user, original_url)
