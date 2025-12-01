from typing import Optional
from urllib.parse import unquote
from urllib.request import Request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from rest_framework import authentication, exceptions

from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import UserSessionPayload


def extract_user_session_from_request(
    request: Request, max_age: int = settings.REFRESH_TOKEN_LIFETIME.total_seconds()
) -> Optional[UserSessionPayload]:
    """
    Extracts the user id from the user_session cookie value. The cookie is signed with a
    TimestampSigner and can be used to verify the user's identity. Look at the
    generate_session_tokens_for_user for more information on how the cookie is signed.
    Ensure your client is sending that value as cookie with the user_session key.

    :param request: The request object.
    :param max_age: The max age of the signed data.
    :return: The user session payload if the cookie is valid, otherwise None.
    """

    cookie = request.COOKIES.get("user_session", None) or ""
    signer = TimestampSigner()

    try:
        return UserSessionPayload(
            **signer.unsign_object(unquote(cookie), max_age=max_age)
        )
    except (BadSignature, SignatureExpired):
        return None


class AuthenticateFromUserSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        """
        Extract the user session payload from the cookie and verify
        that an active user exists and the token created in this
        session is not blacklisted.
        """

        err_msg = "Missing or invalid user session."

        user_session = extract_user_session_from_request(request)
        if user_session is None:
            raise exceptions.AuthenticationFailed(err_msg)

        user_model = get_user_model()
        try:
            user = user_model.objects.select_related("profile").get(
                id=user_session.user_id
            )
        except user_model.DoesNotExist:
            raise exceptions.AuthenticationFailed(err_msg)

        if not user.is_active or UserHandler().refresh_token_hash_is_blacklisted(
            user_session.token_hash
        ):
            raise exceptions.AuthenticationFailed(err_msg)

        return user, request
