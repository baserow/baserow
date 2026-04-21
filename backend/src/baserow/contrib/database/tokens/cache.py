from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from baserow.contrib.database.tokens.models import Token

_KEY_PREFIX = "db_token:"


def _cache_key(token_key: str) -> str:
    # Hash the token key so raw API tokens don't sit in Redis cache keys.
    digest = hashlib.sha256(token_key.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def get_cached_token(token_key: str) -> Token | None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None

    token = cache.get(_cache_key(token_key))
    if token is not None:
        # The key is not stored for security reasons, so we set it here.
        token.key = token_key
    return token


def set_cached_token(token: Token, ttl: int | None = None) -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return

    # Don't store the key in the cache for security reasons.
    token_key = token.key
    token.key = ""

    cache.set(
        _cache_key(token_key),
        token,
        timeout=ttl or settings.BASEROW_CACHE_TTL_SECONDS,
    )

    # Restore the key on the token instance after caching.
    token.key = token_key


def invalidate_cached_token(token_key: str) -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.delete(_cache_key(token_key))
