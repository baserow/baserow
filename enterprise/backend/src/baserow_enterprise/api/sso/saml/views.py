from typing import Any, Dict
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.exceptions import RequestBodyValidationException
from baserow.api.schemas import get_error_schema
from baserow.core.auth_provider.exceptions import DifferentAuthProvider
from baserow.core.exceptions import WorkspaceInvitationEmailMismatch
from baserow.core.user.exceptions import DeactivatedUserException, DisabledSignupError
from baserow_enterprise.api.sso.saml.errors import ERROR_SAML_INVALID_LOGIN_REQUEST
from baserow_enterprise.api.sso.saml.serializers import SAMLResponseSerializer
from baserow_enterprise.api.sso.serializers import SsoLoginRequestSerializer
from baserow_enterprise.api.sso.utils import (
    SsoErrorCode,
    map_sso_exceptions,
    redirect_to_sign_in_error_page,
    redirect_user_on_success,
    urlencode_query_params,
)
from baserow_enterprise.sso.saml.exceptions import (
    InvalidSamlConfiguration,
    InvalidSamlRequest,
    InvalidSamlResponse,
)
from baserow_enterprise.sso.saml.handler import SamlAuthProviderHandler
from baserow_enterprise.sso.utils import (
    check_sso_feature_is_active_or_raise,
    is_sso_feature_active,
)


class AssertionConsumerServiceView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Auth"],
        request=SAMLResponseSerializer,
        operation_id="auth_provider_saml_acs_url",
        description=(
            "Complete the SAML authentication flow by validating the SAML response. "
            "Sign in the user if already exists in Baserow or create a new one otherwise. "
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
    @map_sso_exceptions(
        {
            InvalidSamlConfiguration: SsoErrorCode.INVALID_SAML_RESPONSE,
            InvalidSamlResponse: SsoErrorCode.INVALID_SAML_RESPONSE,
            DeactivatedUserException: SsoErrorCode.USER_DEACTIVATED,
            DifferentAuthProvider: SsoErrorCode.DIFFERENT_PROVIDER,
            RequestBodyValidationException: SsoErrorCode.INVALID_SAML_RESPONSE,
            WorkspaceInvitationEmailMismatch: SsoErrorCode.GROUP_INVITATION_EMAIL_MISMATCH,
            DisabledSignupError: SsoErrorCode.SIGNUP_DISABLED,
        }
    )
    @validate_body(SAMLResponseSerializer, return_validated=True)
    def post(self, request: Request, data: Dict[str, str]) -> HttpResponseRedirect:
        if not is_sso_feature_active():
            return redirect_to_sign_in_error_page(SsoErrorCode.FEATURE_NOT_ACTIVE)

        user = SamlAuthProviderHandler.sign_in_user_from_saml_response(
            data["SAMLResponse"], data["saml_request_data"]
        )

        return redirect_user_on_success(user, data["RelayState"])


class BaserowInitiatedSingleSignOn(APIView):
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
            OpenApiParameter(
                name="workspace_invitation_token",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "If provided and valid, the user accepts the workspace invitation "
                    "and will have access to the workspace after login or signing up."
                ),
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "An ISO 639 language code (with optional variant) "
                    "selected by the user. Ex: en-GB."
                ),
            ),
        ],
        tags=["Auth"],
        request=SsoLoginRequestSerializer,
        operation_id="auth_provider_saml_sp_login",
        description=(
            "This is the endpoint that is called when the user wants to initiate a "
            "SSO SAML login from Baserow (the service provider). The user will be "
            "redirected to the SAML identity provider (IdP) where the user can authenticate. "
            "Once logged in in the IdP, the user will be redirected back "
            "to the assertion consumer service endpoint (ACS) where the SAML response "
            "will be validated and a new JWT session token will be provided to work with "
            "Baserow APIs."
        ),
        responses={302: None},
        auth=[],
    )
    @map_sso_exceptions(
        {
            InvalidSamlConfiguration: SsoErrorCode.INVALID_SAML_REQUEST,
            InvalidSamlRequest: SsoErrorCode.INVALID_SAML_REQUEST,
            RequestBodyValidationException: SsoErrorCode.INVALID_SAML_REQUEST,
        }
    )
    @validate_query_parameters(SsoLoginRequestSerializer, return_validated=True)
    def get(
        self, request: Request, query_params: Dict[str, str]
    ) -> HttpResponseRedirect:
        if not is_sso_feature_active():
            return redirect_to_sign_in_error_page(SsoErrorCode.FEATURE_NOT_ACTIVE)

        idp_sign_in_url = SamlAuthProviderHandler.get_sign_in_url(query_params)
        return redirect(idp_sign_in_url)


class AdminAuthProvidersLoginUrlView(APIView):
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
                    "The url to which the user should be redirected after a successful login."
                ),
            ),
            OpenApiParameter(
                name="workspace_invitation_token",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "If provided and valid, the user accepts the workspace invitation "
                    "and will have access to the workspace after login or signing up."
                ),
            ),
            OpenApiParameter(
                name="language",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description=(
                    "An ISO 639 language code (with optional variant) "
                    "selected by the user. Ex: en-GB."
                ),
            ),
        ],
        tags=["Auth"],
        request=SsoLoginRequestSerializer,
        operation_id="auth_provider_login_url",
        description=(
            "Return the correct redirect_url to initiate the SSO SAML login. "
            "It needs an email address if multiple SAML providers are configured otherwise "
            "the only configured SAML provider signup URL will be returned."
        ),
        responses={
            200: Dict[str, str],
            400: get_error_schema(["ERROR_SAML_INVALID_LOGIN_REQUEST"]),
        },
        auth=[],
    )
    @validate_query_parameters(SsoLoginRequestSerializer, return_validated=True)
    @map_exceptions(
        {
            InvalidSamlRequest: ERROR_SAML_INVALID_LOGIN_REQUEST,
        }
    )
    def get(self, request: Request, query_params: Dict[str, Any]) -> Response:
        """Return the correct URL to initiate a SSO SAML login from baserow."""

        check_sso_feature_is_active_or_raise()

        # raises if no valid SAML provider configured for the email provided is found
        SamlAuthProviderHandler.get_saml_auth_provider_from_email(
            query_params.get("email")
        )

        saml_login_url = urljoin(
            settings.PUBLIC_BACKEND_URL, reverse("api:enterprise_sso_saml:login")
        )
        saml_login_url = urlencode_query_params(saml_login_url, query_params)
        return Response({"redirect_url": saml_login_url})
