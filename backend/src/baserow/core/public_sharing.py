"""
Helpers for the non-expiring JWT tokens that grant access to password protected,
publicly shared resources, like views and dashboards.

The secret of a token is derived from the slug and the password hash of the shared
resource, so rotating the slug or changing the password invalidates every token
that was handed out before. The server's `SECRET_KEY` is mixed in so that a token
cannot be forged by someone who knows the slug and the hash.
"""

from typing import Any, Dict

from django.conf import settings

import jwt

PUBLIC_ACCESS_TOKEN_ALGORITHM = "HS256"  # nosec


def _get_public_access_token_secret(slug: str, password_hash: str) -> str:
    return f"{slug}-{password_hash}-{settings.SECRET_KEY}"


def encode_public_access_token(slug: str, password_hash: str) -> str:
    """
    Creates a non-expiring JWT token that authorizes public requests for the
    resource with the given slug.

    :param slug: The slug of the publicly shared resource.
    :param password_hash: The hash of the password that protects the resource.
    :return: The encoded token.
    """

    return jwt.encode(
        {"slug_id": slug},
        key=_get_public_access_token_secret(slug, password_hash),
        algorithm=PUBLIC_ACCESS_TOKEN_ALGORITHM,
    )


def decode_public_access_token(
    slug: str, password_hash: str, token: str
) -> Dict[str, Any]:
    """
    Decodes the token with the secret of the resource.

    :param slug: The slug of the publicly shared resource.
    :param password_hash: The hash of the password that protects the resource.
    :param token: The token to decode.
    :raises jwt.InvalidTokenError: If the token was not issued for this slug and
        password hash.
    :return: The decoded payload.
    """

    return jwt.decode(
        token,
        key=_get_public_access_token_secret(slug, password_hash),
        algorithms=[PUBLIC_ACCESS_TOKEN_ALGORITHM],
    )


def is_public_access_token_valid(slug: str, password_hash: str, token: str) -> bool:
    """
    Checks whether the token grants access to the resource with the given slug
    and password hash.

    :param slug: The slug of the publicly shared resource.
    :param password_hash: The hash of the password that protects the resource.
    :param token: The token to check.
    :return: True if the token is valid for the resource, False otherwise.
    """

    try:
        decode_public_access_token(slug, password_hash, token)
        return True
    except jwt.InvalidTokenError:
        return False
