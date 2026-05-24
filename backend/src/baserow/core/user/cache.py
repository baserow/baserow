from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

_KEY_PREFIX = "user:"


def _cache_key(user_id: int) -> str:
    return f"{_KEY_PREFIX}{user_id}"


def get_cached_user(user_id: int) -> AbstractUser | None:
    """
    Return a cached User instance (with profile pre-loaded) or ``None`` on
    cache miss or when caching is disabled.
    """

    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None
    return cache.get(_cache_key(user_id))


def set_cached_user(user: AbstractUser) -> None:
    """
    Store *user* (with its pre-loaded profile) in Redis.  No-op when the
    cache TTL is 0 or negative.
    """

    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.set(
        _cache_key(user.id),
        user,
        timeout=settings.BASEROW_CACHE_TTL_SECONDS,
    )


def invalidate_cached_user(user_id: int) -> None:
    """
    Invalidate the cached User instance for the given user ID.  No-op when the
    cache TTL is 0 or negative.
    """

    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.delete(_cache_key(user_id))
