import uuid
from urllib.parse import parse_qs

from django.conf import settings

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

# Nosec disables spurious hardcoded password warning, this is not a password but instead
# the value of the JWT token to be used when a user wants to connect anonymously.
ANONYMOUS_USER_TOKEN = "anonymous"  # nosec


@database_sync_to_async
def get_user(token):
    """
    Selects a user related to the provided JWT token. If the token is invalid or if the
    user does not exist then None is returned.

    :param token: The JWT token for which the user must be fetched.
    :type token: str
    :return: The user related to the JWT token.
    :rtype: User or None
    """

    from baserow.api.user.jwt import get_user_from_token

    anonymous = token == ANONYMOUS_USER_TOKEN
    if anonymous:
        if settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
            return
        else:
            from django.contrib.auth.models import AnonymousUser

            return AnonymousUser()
    else:
        try:
            return get_user_from_token(token)
        except (TokenError, InvalidToken):
            return


class JWTTokenAuthMiddleware(BaseMiddleware):
    """
    The auth middleware adds a user object to the scope if a valid JWT token is
    provided via the GET parameters when requesting the web socket. It also adds a
    web_socket_id taken from the query parameter or generated as a random UUID.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_params = parse_qs(scope["query_string"].decode("utf8"))
        scope["user"] = None
        scope["web_socket_id"] = None

        jwt_token = query_params.get("jwt_token")
        if jwt_token:
            scope["user"] = await get_user(jwt_token[0])

        if scope["user"] is not None:
            web_socket_id = query_params.get("web_socket_id")
            scope["web_socket_id"] = (
                web_socket_id[0] if web_socket_id else str(uuid.uuid4())
            )

        return await self.inner(scope, receive, send)
