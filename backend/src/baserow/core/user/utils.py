import unicodedata
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.core.signing import TimestampSigner

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from baserow.core.registries import subject_type_registry
from baserow.core.types import Actor
from baserow.core.utils import generate_hash


@dataclass
class UserSessionPayload:
    user_id: int
    token_hash: str
    # Sessions signed before refresh tokens were rotated don't have these.
    session_hash: Optional[str] = None
    expires_at: Optional[int] = None


def normalize_email_address(email):
    """
    Normalizes an email address by stripping the whitespace, converting to lowercase
    and by normalizing the unicode.

    :param email: The email address that needs to be normalized.
    :type email: str
    :return: The normalized email address.
    :rtype: str
    """

    return unicodedata.normalize("NFKC", email).strip().lower()


# Holds the id of the staff member the token was issued to.
IMPERSONATED_BY_CLAIM = "impersonated_by"
IMPERSONATED_BY_USER_ATTR = "impersonated_by_user_id"
# Holds the id of the login a rotated refresh token descends from.
SESSION_ID_CLAIM = "session_id"
# Signs user sessions that carry a session hash. Releases before refresh token
# rotation can't read those, and the salt makes them reject them as invalid.
USER_SESSION_SALT = "baserow.user_session"


def get_refresh_token_session_hash(refresh_token: RefreshToken) -> str:
    """
    :param refresh_token: A refresh token of the session.
    :return: The hash under which the session of the token is blacklisted.
    """

    # Tokens issued before rotation have no session claim, their own id is then
    # the session id.
    session_id = refresh_token.get(SESSION_ID_CLAIM) or refresh_token.get(
        jwt_settings.JTI_CLAIM
    )
    return generate_hash(f"session:{session_id}")


def set_user_impersonated_from_token(user: AbstractUser, token) -> None:
    """
    Remembers on the user object, for this request only, which staff member the
    token was issued to when the user is being impersonated.

    :param user: The authenticated user.
    :param token: The validated access token of the request.
    """

    setattr(user, IMPERSONATED_BY_USER_ATTR, token.get(IMPERSONATED_BY_CLAIM))


def get_impersonated_by_user_id(user: AbstractUser) -> Optional[int]:
    """
    :param user: The authenticated user of the request.
    :return: The id of the staff member impersonating the user, or `None`.
    """

    return getattr(user, IMPERSONATED_BY_USER_ATTR, None)


def is_user_impersonated(user: AbstractUser) -> bool:
    return get_impersonated_by_user_id(user) is not None


def generate_session_tokens_for_user(
    user: AbstractUser,
    include_refresh_token: bool = False,
    verified_email_claim: Optional[str] = None,
    impersonated_by_user_id: Optional[int] = None,
) -> Dict[str, str]:
    """
    Generates a new access and refresh token (if requested) for the given user.

    :param user: The user for which the tokens must be generated.
    :param include_refresh_token: Whether or not a refresh token must be included.
    :param verified_email_claim: Optionally stores which authentication
        method was used.
    :param impersonated_by_user_id: The id of the staff member acting as this
        user, if any. Marks the tokens, so requests made with them can be told
        apart from the user's own.
    :return: A dictionary with the access and refresh token.
    """

    access_token = AccessToken.for_user(user)
    refresh_token = RefreshToken.for_user(user) if include_refresh_token else None

    if refresh_token and verified_email_claim is not None:
        refresh_token["verified_email_claim"] = verified_email_claim

    if impersonated_by_user_id is not None:
        access_token[IMPERSONATED_BY_CLAIM] = impersonated_by_user_id
        if refresh_token:
            refresh_token[IMPERSONATED_BY_CLAIM] = impersonated_by_user_id

    return prepare_user_tokens_payload(user.id, access_token, refresh_token)


def sign_user_session(user_id: int, refresh_token: str) -> str:
    """
    Signs the given user session using the Django signing backend.
    This session can be used to verify the user's identity in a cookie and will
    be valid for the same time of the refresh_token lifetime or until the user
    logs out (blacklisting the token).

    NOTE: Don't use this payload to authenticate users in the API, especially
    for operations that can change the user's state, to avoid CSRF attacks.
    This payload is only meant to be used to verify the user's identity in a
    cookie for GET requests when the Authorization header is not available.

    :param user_id: The user id that must be signed.
    :param refresh_token: The refresh token defining the session. An hash of this
        token will be stored in the session to keep it secure.
    :return: The signed user id.
    """

    payload = UserSessionPayload(str(user_id), generate_hash(refresh_token))
    try:
        token = RefreshToken(refresh_token)
    except TokenError:
        return TimestampSigner().sign_object(asdict(payload))

    # A rotated refresh token keeps the expiry of the first one, while the
    # signature would otherwise be valid for a full lifetime from now.
    payload.session_hash = get_refresh_token_session_hash(token)
    payload.expires_at = token["exp"]
    return TimestampSigner(salt=USER_SESSION_SALT).sign_object(asdict(payload))


def prepare_user_tokens_payload(
    user_id: int,
    access_token: Union[AccessToken, str],
    refresh_token: Optional[Union[RefreshToken, str]] = None,
) -> Dict[str, str]:
    """
    Generates a new access and refresh token (if requested) for the given user.
    For backward compatibility the access token is also returned under the key
    `token` (deprecated).

    :param user_id: The user id for which the tokens must be generated.
    :param access_token: The access token that must be returned.
    :param refresh_token: The refresh token that must be returned.
    :return: A dictionary with the access and refresh token.
    """

    session_tokens = {
        "token": str(access_token),
        "access_token": str(access_token),
    }

    if refresh_token:
        session_tokens["refresh_token"] = str(refresh_token)
        session_tokens["user_session"] = sign_user_session(user_id, str(refresh_token))

    return session_tokens


def language_for_actor(actor: Actor | None) -> str | None:
    """
    Returns the language of the user an actor is stored as.

    :param actor: The acting subject, or None.
    :return: Its profile language, or None to use the default language.
    """

    user = subject_type_registry.user_for_actor(actor)
    return user.profile.language if user is not None else None
