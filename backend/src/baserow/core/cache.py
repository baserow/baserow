from contextlib import contextmanager
from typing import Callable, TypeVar

from django.conf import settings

from asgiref.local import Local

T = TypeVar("T")


class LocalCache:
    """
    A thread-safe and async-safe local cache implementation using asgiref.Local.

    This cache provides request-scoped storage in Django applications via the
    LocalCacheMiddleware. It ensures that data is isolated between different requests
    and is automatically cleaned up after each request cycle, preventing data leakage
    and maintaining proper cache lifecycle management.
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

        cache = self._local.cache

        if key not in cache:
            value = default() if callable(default) else default
            cache[key] = value

        return cache[key]

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
