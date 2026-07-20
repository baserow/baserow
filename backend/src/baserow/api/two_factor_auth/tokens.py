from django.conf import settings

from rest_framework import permissions
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import Token


class TwoFactorAccessToken(Token):
    token_type = "2fa"  # nosec
    lifetime = settings.ACCESS_TOKEN_LIFETIME


class Require2faToken(permissions.BasePermission):
    """
    Require that the provided JWT is a two factor access token and extract
    the user identity from it. Sets ``request.two_factor_user_id`` so
    downstream views can resolve the authenticated user from the token
    rather than trusting client-supplied fields.
    """

    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token_string = auth_header.split(" ")[1]

        try:
            token = TwoFactorAccessToken(token_string)
            if token.token_type != "2fa":  # nosec
                return False
            request.two_factor_user_id = token.payload["user_id"]
            return True
        except (InvalidToken, TokenError, KeyError):
            return False
