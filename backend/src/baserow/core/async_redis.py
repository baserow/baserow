"""
Async Redis clients for code running on the event loop.

There are two, because they address two different stores:

``get_async_redis``
    Data Baserow itself writes, such as websocket presence.  It follows
    ``REDIS_URL`` and decodes responses, because those values are text.

``get_async_cache_redis``
    Values django-redis wrote through Django's cache framework.  It follows the
    default cache's own location and leaves responses undecoded, because those
    values are pickled.

Pick by who wrote the value you are reading, not by which one is closer to hand.
"""

import asyncio
from weakref import WeakKeyDictionary

from django.conf import settings

from redis.asyncio import Redis, from_url

_Pools = WeakKeyDictionary[asyncio.AbstractEventLoop, Redis]

_pools: _Pools = WeakKeyDictionary()
_cache_pools: _Pools = WeakKeyDictionary()
_test_override: Redis | None = None
_cache_test_override: Redis | None = None


async def _get_pooled_client(pools: _Pools, url: str, decode_responses: bool) -> Redis:
    """
    Return the client this event loop owns, creating it on first use.

    Each loop gets its own client because ``redis.asyncio`` pins connections to
    the loop that created them.  Dead loops are evicted automatically via
    ``WeakKeyDictionary``.

    :param pools: The per-loop client map to look in.
    :param url: The Redis URL to connect to when no client exists yet.
    :param decode_responses: Whether replies should be decoded as text.
    :return: The client bound to the running loop.
    """

    loop = asyncio.get_running_loop()
    client = pools.get(loop)
    if client is None:
        client = from_url(url, decode_responses=decode_responses)
        pools[loop] = client
    return client


def get_cache_redis_url() -> str:
    """
    Return the URL of the Redis instance backing Django's default cache.

    Reading the cache's own location rather than ``REDIS_URL`` keeps the async
    reader on the same server and database as django-redis even when the cache
    is pointed somewhere else.

    :return: The connection URL of the default cache.
    """

    location = settings.CACHES["default"]["LOCATION"]
    if isinstance(location, (list, tuple)):
        return location[0]
    return location


async def get_async_redis() -> Redis:
    """
    Return a shared async Redis client for values Baserow wrote itself.

    :return: The text client bound to the running loop.
    """

    if _test_override is not None:
        return _test_override
    return await _get_pooled_client(_pools, settings.REDIS_URL, decode_responses=True)


async def get_async_cache_redis() -> Redis:
    """
    Return a shared async Redis client for values Django's cache wrote.

    :return: The undecoded client bound to the running loop.
    """

    if _cache_test_override is not None:
        return _cache_test_override
    return await _get_pooled_client(
        _cache_pools, get_cache_redis_url(), decode_responses=False
    )


def set_async_redis(client: Redis | None) -> None:
    """
    Replace the shared pool — used by tests to inject a fake client.

    The override is loop-agnostic: it bypasses the per-loop map entirely.

    :param client: The client to use, or ``None`` to restore the real pool.
    """

    global _test_override
    _test_override = client


def set_async_cache_redis(client: Redis | None) -> None:
    """
    Replace the shared cache pool — used by tests to inject a fake client.

    :param client: The client to use, or ``None`` to restore the real pool.
    """

    global _cache_test_override
    _cache_test_override = client
