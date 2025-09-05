from contextlib import contextmanager
from typing import Callable, TypeVar

from django.conf import settings
from django.core.cache import cache

from asgiref.local import Local
from loguru import logger
from redis.exceptions import LockNotOwnedError

from baserow.version import VERSION as BASEROW_VERSION

T = TypeVar("T")

# This var is to invalidate global cache when we can't bump the Baserow version for
# some reason.
GLOBAL_CACHE_VERSION = 2


class LocalCache:
    """
    A thread-safe and async-safe local cache implementation using asgiref.Local.

    This cache provides request-scoped storage in Django applications via the
    LocalCacheMiddleware. It ensures that data is isolated between different requests
    and is automatically cleaned up after each request cycle, preventing data leakage
    and maintaining proper cache lifecycle management.

    Example Usage:

        # Storing and retrieving a value
        value = local_cache.get(
            "user_123_data",
            default=lambda: expensive_computation()
        )

        # Context manager
        with local_cache.context():
           # The cache is cleared before and at the end of this block
    """

    def __init__(self):
        self._local = Local()

    def get(self, key: str, default: T | Callable[[], T] = None) -> T:
        """
        Get a value from the cache. If the key is not present:
        - If the default is callable, call it to get the value.
        - Otherwise, use the plain default value.
        The computed or plain default value is stored in the cache.
        As the cache is shared, ensure the key is unique to prevent collision.
        """

        if not settings.BASEROW_USE_LOCAL_CACHE:
            return default() if callable(default) else default

        if not hasattr(self._local, "cache"):
            self._local.cache = {}

        cached = self._local.cache

        if key not in cached:
            logger.debug(f"Local cache miss {key}")
            value = default() if callable(default) else default
            cached[key] = value
        else:
            logger.debug(f"Local cache hit {key}")

        return cached[key]

    def delete(self, key: str):
        """
        Delete a value from the cache. If the key does not exist, no action is taken.
        If the key ends with "*", all keys starting with the prefix are deleted.

        :param key: The key to delete from the cache.
        """

        if not hasattr(self._local, "cache"):
            return

        logger.debug(f"Local cache key deletion for: {key}")

        if key.endswith("*"):
            for k in list(
                filter(lambda k: k.startswith(key[:-1]), self._local.cache.keys())
            ):
                del self._local.cache[k]
        else:
            if key in self._local.cache:
                del self._local.cache[key]

    def clear(self):
        """
        Clear all data from the cache.
        """

        if hasattr(self._local, "cache"):
            del self._local.cache

    @contextmanager
    def context(self):
        """
        Context manager for automatic cache lifecycle management. Clears the cache
        before entering the context and ensures cleanup after exiting, even if an
        exception occurs.
        """

        self.clear()
        try:
            yield self
        finally:
            self.clear()


local_cache = LocalCache()


class LocalCacheMiddleware:
    """
    Django middleware for managing the lifecycle of LocalCache.

    This middleware ensures that the cache is cleared before and after
    each request, preventing data leakage between requests and maintaining
    proper cleanup.

    Usage:
        Add to MIDDLEWARE in Django settings:
        'baserow.core.cache.LocalCacheMiddleware'
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with local_cache.context():
            return self.get_response(request)


SENTINEL = object()


class GlobalCache:
    """
    A global cache wrapper around the Django cache system that provides
    invalidation capabilities and a lock mechanism to prevent multiple
    concurrent updates. It's also versioned with Baserow version.

    Be careful to make sure all values used in the callback should be part of the key
    otherwise you may experience inconsistency.

    Example Usage:

        # Storing and retrieving a value
        value = global_cache.get(
            "user_123_data",
            default=lambda: expensive_computation(),
            timeout=300
        )

        # Invalidating a cache key
        global_cache.invalidate("user_123_data")
    """

    VERSION_KEY_TTL = 60 * 60 * 24 * 10  # 10 days

    def _get_version_cache_key(
        self, key: str, invalidate_key: None | str = None
    ) -> str:
        """
        Generates a versioned cache key for tracking different versions of a cached
        value.

        :param key: The base cache key.
        :param invalidate_key: The key used when this cache is invalidated.
        :return: A modified cache key used for version tracking.
        """

        key = key if invalidate_key is None else invalidate_key

        return f"{BASEROW_VERSION}_{GLOBAL_CACHE_VERSION}_{key}__current_version"

    def _get_cache_key_with_version(self, key: str) -> str:
        """
        Generates a cache key with included version.

        :param key: The base cache key.
        :return: A modified cache key with version.
        """

        version = cache.get(self._get_version_cache_key(key), 0)
        return f"{BASEROW_VERSION}_{GLOBAL_CACHE_VERSION}_{key}__version_{version}"

    def _get_versioned_cache_key(
        self, key: str, invalidate_key: None | str = None
    ) -> str:
        version_key = self._get_version_cache_key(key, invalidate_key)

        version = cache.get(version_key, 0)

        cache_key_to_use = (
            f"{BASEROW_VERSION}_{GLOBAL_CACHE_VERSION}_{key}__version_{version}"
        )

        return cache_key_to_use

    def get(
        self,
        key: str,
        default: T | Callable[[], T] = None,
        invalidate_key: None | str = None,
        timeout: int = 60,
    ) -> T:
        """
        Retrieves a value from the cache if it exists; otherwise, sets it using the
        provided default value.

        This function also uses a lock (if available on the cache backend) to ensure
        multi call safety when setting a new value.

        :param key: The key of the cache value to get (or set). Make sure this key is
            unique and not used elsewhere.
        :param invalidate_key: The key used when this cache is invalidated. A default
            one is used if none is provided and this value otherwise. Can be used to
            invalidate multiple caches at the same time. When invalidating the cache you
            must use the same key later.
        :param default: The default value to store in the cache if the key is absent.
                        Can be either a literal value or a callable. If it's a callable,
                        the function is called to retrieve the default value.
        :param timeout: The cache timeout in seconds for newly set values.
           Defaults to 60.
        :return: The cached value if it exists; otherwise, the newly set value.
        """

        cache_key_to_use = self._get_versioned_cache_key(key, invalidate_key)
        cached = cache.get(cache_key_to_use, SENTINEL)

        if cached is SENTINEL:
            use_lock = hasattr(cache, "lock")
            if use_lock:
                cache_lock = cache.lock(f"{cache_key_to_use}__lock", timeout=10)
                cache_lock.acquire()
            try:
                cached = cache.get(cache_key_to_use, SENTINEL)
                # We check again to make sure it hasn't been populated in the meantime
                # while acquiring the lock
                if cached is SENTINEL:
                    logger.debug(f"Global cache miss for: {key}")
                    if callable(default):
                        cached = default()
                    else:
                        cached = default

                    cache.set(
                        cache_key_to_use,
                        cached,
                        timeout=timeout,
                    )
                else:
                    logger.debug(f"Global cache hit for: {key}")
            finally:
                if use_lock:
                    try:
                        cache_lock.release()
                    except LockNotOwnedError:
                        # If the lock release fails, it might be because of the timeout
                        # and it's been stolen so we don't really care
                        pass
        else:
            logger.debug(f"Global cache hit for: {key}")

        return cached

    def update(
        self,
        key: str,
        callback: Callable[[T], T],
        default_value: T | Callable[[], T] = None,
        invalidate_key: None | str = None,
        timeout: int = 60,
    ) -> T:
        cache_key_to_use = self._get_versioned_cache_key(key, invalidate_key)

        use_lock = hasattr(cache, "lock")
        if use_lock:
            cache_lock = cache.lock(f"{cache_key_to_use}__lock", timeout=10)
            cache_lock.acquire()

        try:
            default = default_value() if callable(default_value) else default_value
            initial_value = cache.get(cache_key_to_use, default)
            new_value = callback(initial_value)
            cache.set(
                cache_key_to_use,
                new_value,
                timeout=timeout,
            )
        finally:
            if use_lock:
                try:
                    cache_lock.release()
                except LockNotOwnedError:
                    # If the lock release fails, it might be because of the timeout
                    # and it's been stolen so we don't really care
                    pass

        return new_value

    def invalidate(self, key: None | str = None, invalidate_key: None | str = None):
        """
        Invalidates the cached value associated with the given key, ensuring that
        subsequent cache reads will miss and require a new value to be set.

        :param key: The cache key to invalidate.
        :param invalidate_key: The key to use for invalidation. If provided, this key
            must match the one given at cache creation.
        """

        version_key = self._get_version_cache_key(key, invalidate_key)

        logger.debug(f"Global cache invalidation for: {key or invalidate_key}")

        try:
            cache.incr(version_key, 1)
        except ValueError:
            # If the cache key does not exist, initialize its versioning.
            cache.set(
                version_key,
                1,
                timeout=self.VERSION_KEY_TTL,
            )


global_cache = GlobalCache()
