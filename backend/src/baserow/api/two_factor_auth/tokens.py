from django.conf import settings

from rest_framework import permissions
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import Token


class TwoFactorAccessToken(Token):
    token_type = "2fa"  # nosec
    lifetime = settings.ACCESS_TOKEN_LIFETIME


class Require2faToken(permissions.BasePermission):
    """
    Require that the provided JWT is two factor access token type.
    """

    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token_string = auth_header.split(" ")[1]

        try:
            token = TwoFactorAccessToken(token_string)
            return token.token_type == "2fa"  # nosec
        except (InvalidToken, TokenError):
            return False
