from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from baserow.contrib.database.tokens.models import Token

_KEY_PREFIX = "db_token:"


def _cache_key(token_key: str) -> str:
    # Hash the token key so raw API tokens don't sit in Redis in cleartext.
    digest = hashlib.sha256(token_key.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def get_cached_token(token_key: str) -> Token | None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None
    return cache.get(_cache_key(token_key))


def set_cached_token(token: Token, ttl: int | None = None) -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.set(
        _cache_key(token.key),
        token,
        timeout=ttl or settings.BASEROW_CACHE_TTL_SECONDS,
    )


def invalidate_cached_token(token_key: str) -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.delete(_cache_key(token_key))
