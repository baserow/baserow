import asyncio
from weakref import WeakKeyDictionary

from django.conf import settings

from redis.asyncio import Redis, from_url

_pools: WeakKeyDictionary[asyncio.AbstractEventLoop, Redis] = WeakKeyDictionary()
_test_override: Redis | None = None


async def get_async_redis() -> Redis:
    """
    Return a shared async Redis client for the current event loop.

    Each loop gets its own client because ``redis.asyncio`` pins
    connections to the loop that created them.  Dead loops are evicted
    automatically via ``WeakKeyDictionary``.
    """

    if _test_override is not None:
        return _test_override

    loop = asyncio.get_running_loop()
    client = _pools.get(loop)
    if client is None:
        client = from_url(settings.REDIS_URL, decode_responses=True)
        _pools[loop] = client
    return client


def set_async_redis(client: Redis | None) -> None:
    """
    Replace the shared pool — used by tests to inject a fake client.

    The override is loop-agnostic: it bypasses the per-loop map entirely.
    """

    global _test_override
    _test_override = client
