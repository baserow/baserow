from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import Token

User = get_user_model()


class TwoFactorAccessToken(Token):
    token_type = "2fa"  # nosec
    lifetime = settings.ACCESS_TOKEN_LIFETIME


class TwoFactorTokenAuthentication(BaseAuthentication):
    """
    Authenticates the request by validating a 2FA JWT from the
    Authorization header and resolving the user from the token payload.
    """

    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token_string = auth_header.split(" ")[1]

        try:
            token = TwoFactorAccessToken(token_string)
        except (InvalidToken, TokenError):
            raise exceptions.AuthenticationFailed("Invalid 2FA token.")

        try:
            user_id = token.payload[jwt_settings.USER_ID_CLAIM]
        except KeyError:
            raise exceptions.AuthenticationFailed(
                "Token contained no recognizable user identification."
            )

        user = User.objects.filter(
            **{jwt_settings.USER_ID_FIELD: user_id}, is_active=True
        ).first()
        if not user:
            raise exceptions.AuthenticationFailed("User not found or inactive.")

        return (user, token)
