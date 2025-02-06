from typing import Any, Callable

from asgiref.local import Local

# Thread/Async-local storage
_local = Local()


def get_short_cache(key: str, default: Any | Callable = None):
    """
    Get a value from the short cache. If the key is not present:
      - If the default is callable, call it to get the value.
      - Otherwise, use the plain default value.
    The computed or plain default value is stored in the cache.
    As the cache is shared, ensure the key is unique to prevent collision.
    """

    if not hasattr(_local, "cache"):
        _local.cache = {}
    cache = _local.cache

    if key not in cache:
        value = default() if callable(default) else default
        cache[key] = value

    return cache[key]


def clear_short_cache():
    """Clear the short cache (cleanup)."""

    if hasattr(_local, "cache"):
        del _local.cache


class ShortCacheMiddleware:
    """Middleware to manage thread/async-local cache for each request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Clear short cache before each request
        clear_short_cache()

        try:
            response = self.get_response(request)
        finally:
            # And after
            clear_short_cache()

        return response
