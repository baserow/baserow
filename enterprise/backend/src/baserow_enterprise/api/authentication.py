import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote
from urllib.request import Request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import (
    BadSignature,
    SignatureExpired,
    TimestampSigner,
    b62_decode,
)

from rest_framework import authentication, exceptions

from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import USER_SESSION_SALT, UserSessionPayload


@dataclass
class VerifiedUserSession(UserSessionPayload):
    # The unix timestamp in seconds at which the cookie was signed. It's not part
    # of the signed payload, so cookies of every release have it.
    signed_at: Optional[int] = None


def extract_user_session_from_request(
    request: Request, max_age: int = settings.REFRESH_TOKEN_LIFETIME.total_seconds()
) -> Optional[VerifiedUserSession]:
    """
    Extracts the user id from the user_session cookie value. The cookie is signed with a
    TimestampSigner and can be used to verify the user's identity. Look at the
    generate_session_tokens_for_user for more information on how the cookie is signed.
    Ensure your client sends that value using the configured frontend cookie prefix
    followed by the ``user_session`` key.

    :param request: The request object.
    :param max_age: The max age of the signed data.
    :return: The user session payload and when it was signed if the cookie is
        valid, otherwise None.
    """

    cookie_name = f"{settings.FRONTEND_COOKIE_PREFIX}user_session"
    cookie = unquote(request.COOKIES.get(cookie_name, None) or "")

    # Sessions signed before refresh tokens were rotated use the default salt.
    for signer in (TimestampSigner(salt=USER_SESSION_SALT), TimestampSigner()):
        try:
            payload = signer.unsign_object(cookie, max_age=max_age)
        except (BadSignature, SignatureExpired):
            continue
        # The cookie is `<payload>:<timestamp>:<signature>` and the signature that
        # was just verified covers the timestamp.
        signed_at = b62_decode(cookie.rsplit(signer.sep, 2)[1])
        return VerifiedUserSession(**payload, signed_at=signed_at)
    return None


class AuthenticateFromUserSessionAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        """
        Extract the user session payload from the cookie and verify
        that an active user exists, the token created in this
        session is not blacklisted and the password hasn't changed since the
        cookie was signed.
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

        handler = UserHandler()
        if (
            not user.is_active
            # A session hash keeps the cookie valid while the refresh token
            # rotates, signing off revokes the whole session.
            or handler.refresh_token_hash_is_blacklisted(
                user_session.session_hash or user_session.token_hash
            )
            or (user_session.expires_at and user_session.expires_at < time.time())
            # Like the tokens, a cookie signed before the password changed must
            # stop working.
            or user.profile.iat_before_last_password_change(user_session.signed_at)
        ):
            raise exceptions.AuthenticationFailed(err_msg)

        return user, request
