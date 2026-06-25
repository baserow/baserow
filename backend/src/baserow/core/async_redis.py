from django.conf import settings

from redis.asyncio import Redis, from_url

_pool: Redis | None = None


async def get_async_redis() -> Redis:
    """
    Return a shared async Redis client backed by a connection pool.

    Reads ``settings.REDIS_URL`` on first call and reuses the same pool
    for all subsequent calls.  ``decode_responses=True`` so callers work
    with ``str`` instead of ``bytes``.
    """

    global _pool
    if _pool is None:
        _pool = from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


async def close_async_redis() -> None:
    """Shut down the shared pool (call during application teardown)."""

    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def set_async_redis(client: Redis | None) -> None:
    """
    Replace the shared pool — used by tests to inject a fake client.
    """

    global _pool
    _pool = client
