import uuid
from urllib.parse import parse_qs

from django.conf import settings

from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from baserow.core.user.cache import aget_cached_user
from baserow.ws.telemetry import run_database_sync, websocket_phase

# Nosec disables spurious hardcoded password warning, this is not a password but instead
# the value of the JWT token to be used when a user wants to connect anonymously.
ANONYMOUS_USER_TOKEN = "anonymous"  # nosec


async def get_user(token):
    """
    Selects a user related to the provided JWT token. If the token is invalid or if the
    user does not exist then None is returned.

    :param token: The JWT token for which the user must be fetched.
    :type token: str
    :return: The user related to the JWT token.
    :rtype: User or None
    """

    anonymous = token == ANONYMOUS_USER_TOKEN
    if anonymous:
        if settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
            return
        else:
            from django.contrib.auth.models import AnonymousUser

            return AnonymousUser()
    user = await _get_cached_authenticated_user(token)
    if user is not None:
        return user

    return await run_database_sync("authentication", _get_authenticated_user, token)


async def _get_cached_authenticated_user(token):
    """
    Authenticate from the user cache, without a database query or a thread hop.

    Only a positive answer is returned, so every miss and every rejection falls
    through to the authoritative database lookup and a stale entry can never
    lock a valid user out.

    :param token: The JWT token for which the user must be fetched.
    :return: The cached user the token authenticates, or ``None``.
    """

    # The ASGI router imports this module before django.setup(). These helpers
    # import Django models, so load them only when authenticating a connection.
    from rest_framework_simplejwt.tokens import AccessToken

    from baserow.api.user.jwt import user_is_valid_for_token

    try:
        access_token = AccessToken(token)
        user_id = access_token[jwt_settings.USER_ID_CLAIM]
    except (TokenError, InvalidToken, KeyError):
        return None

    user = await aget_cached_user(user_id)
    if user is None or not user_is_valid_for_token(user, access_token):
        return None
    return user


def _get_authenticated_user(token):
    from baserow.api.user.jwt import get_user_from_token

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

        with websocket_phase("authentication"):
            jwt_token = query_params.get("jwt_token")
            if jwt_token:
                scope["user"] = await get_user(jwt_token[0])

        if scope["user"] is not None:
            web_socket_id = query_params.get("web_socket_id")
            scope["web_socket_id"] = (
                web_socket_id[0] if web_socket_id else str(uuid.uuid4())
            )

        return await self.inner(scope, receive, send)
