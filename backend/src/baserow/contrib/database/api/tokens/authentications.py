from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import HTTP_HEADER_ENCODING
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from baserow.api.sessions import set_user_remote_addr_ip_from_request
from baserow.contrib.database.tokens.exceptions import TokenDoesNotExist
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.sentry import setup_user_in_sentry
from baserow.core.telemetry.utils import setup_user_in_baggage_and_spans


class TokenAuthentication(BaseAuthentication):
    """
    Authentication backend that check if a token authorization is provided and if so
    if checks if the provided key exists.
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b"token":
            return None

        if len(auth) == 1:
            msg = "Invalid token header. No token provided."
            raise AuthenticationFailed(
                {"detail": msg, "error": "ERROR_INVALID_TOKEN_HEADER"}
            )
        elif len(auth) > 2:
            msg = "Invalid token header. Token string should not contain spaces."
            raise AuthenticationFailed(
                {"detail": msg, "error": "ERROR_INVALID_TOKEN_HEADER"}
            )

        decoded_key = auth[1].decode(HTTP_HEADER_ENCODING)
        handler = TokenHandler()

        try:
            token = handler.get_by_key(decoded_key)
        except UserNotInWorkspace:
            msg = "The token's user does not belong to the group anymore."
            raise AuthenticationFailed(
                {"detail": msg, "error": "ERROR_TOKEN_GROUP_MISMATCH"}
            )
        except TokenDoesNotExist:
            msg = "The provided token does not exist."
            raise AuthenticationFailed(
                {"detail": msg, "error": "ERROR_TOKEN_DOES_NOT_EXIST"}
            )

        if not token.user.is_active:
            raise AuthenticationFailed(
                {
                    "detail": "The user related to the token is disabled.",
                    "error": "ERROR_USER_NOT_ACTIVE",
                }
            )

        request.user_token = token
        set_user_remote_addr_ip_from_request(token.user, request)
        with setup_user_in_baggage_and_spans(token.user, request):
            setup_user_in_sentry(token.user)
            return token.user, token


class JSONWebTokenAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = (
        "baserow.contrib.database.api.tokens.authentications.TokenAuthentication"
    )
    name = "Database token"
    match_subclasses = True
    priority = -1

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Token your_token",
        }
