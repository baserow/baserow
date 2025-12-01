from django.utils.translation import gettext_lazy as _

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from baserow.api.user.errors import ERROR_INVALID_ACCESS_TOKEN
from baserow.core.sentry import setup_user_in_sentry
from baserow.core.telemetry.utils import setup_user_in_baggage_and_spans
from baserow.core.user.exceptions import DeactivatedUserException

from .sessions import set_user_session_data_from_request


class JSONWebTokenAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """

        try:
            user_id = validated_token[jwt_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            user = self.user_model.objects.select_related("profile").get(
                **{jwt_settings.USER_ID_FIELD: user_id}
            )
        except self.user_model.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                _("User not found"), code="user_not_found"
            )
        return user

    def authenticate(self, request):
        """
        This method is basically a copy of
        rest_framework_simplejwt.authentication.JWTAuthentication.authenticate
        it adds a machine readable errors to the responses.

        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication.  Otherwise returns `None`.
        """

        try:
            auth_response = super().authenticate(request)
            if auth_response is None:
                return None
            user, token = auth_response

            if not user.profile.is_jwt_token_valid(token):
                raise InvalidToken

            if not user.is_active:
                raise DeactivatedUserException()

        except InvalidToken:
            error_code, _, error_message = ERROR_INVALID_ACCESS_TOKEN
            raise exceptions.AuthenticationFailed(
                detail={"detail": error_message, "error": error_code},
                code=error_code,
            )

        set_user_session_data_from_request(user, request)
        with setup_user_in_baggage_and_spans(user, request):
            setup_user_in_sentry(user)
            return user, token


class JSONWebTokenAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "baserow.api.authentication.JSONWebTokenAuthentication"
    name = "JWT"
    match_subclasses = True
    priority = -1

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT your_token",
        }
