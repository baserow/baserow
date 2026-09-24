from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

from loguru import logger

from baserow.core.async_redis import get_async_cache_redis

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


async def aget_cached_user(user_id: int) -> AbstractUser | None:
    """
    Async twin of :func:`get_cached_user` that never blocks the event loop.

    django-redis ships no async client, so the payload is read through the
    shared ``redis.asyncio`` pool and unpacked with django-redis' own key and
    codec helpers, which keeps the prefix, version, compressor and serializer
    from drifting apart.

    :param user_id: The id of the user to look up.
    :return: The cached user, usable without any further database access, or
        ``None`` when it is missing, unreadable or not fully preloaded.
    """

    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None

    try:
        client = cache.client
        redis = await get_async_cache_redis()
        cached = await redis.get(client.make_key(_cache_key(user_id)))
        if cached is None:
            return None
        user = client.decode(cached)
        # An unloaded profile would query the database from the event loop.
        if not type(user).profile.is_cached(user):
            return None
        return user
    except Exception:
        logger.opt(exception=True).debug("Reading the async user cache failed.")
        return None


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
