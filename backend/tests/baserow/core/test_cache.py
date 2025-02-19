from django.http import HttpRequest
from django.test import override_settings

import pytest

from baserow.core.cache import LocalCacheMiddleware, local_cache


# Simulate a Django view
def mock_view(request):
    user_profile = local_cache.get(
        "user_profile", lambda: {"id": 1, "name": "Test User"}
    )
    return user_profile


@pytest.fixture
def middleware():
    """Provide an instance of the middleware."""

    return LocalCacheMiddleware(get_response=mock_view)


def test_cache_storage(middleware):
    """Test that the cache stores and retrieves values correctly."""

    request = HttpRequest()
    response = middleware(request)

    assert response == {"id": 1, "name": "Test User"}

    # Test that the value is cached
    cached_value = local_cache.get("user_profile")
    assert cached_value is None


def test_callable_default():
    """Test that callable defaults are executed and cached."""

    # Check if the callable default was executed
    assert local_cache.get("user_profile", lambda: "test") == "test"


def test_cache_isolation(middleware):
    """Test that the cache is isolated between simulated requests."""

    local_cache.get("user_profile", "before")

    request1 = HttpRequest()
    result = middleware(request1)

    assert result == {"id": 1, "name": "Test User"}
    assert local_cache.get("user_profile", "No Cache") == "No Cache"

    # Simulate a new request and ensure the cache is isolated
    request2 = HttpRequest()
    middleware(request2)

    # Ensure the second request starts with an empty cache
    assert local_cache.get("user_profile", "No Cache") == "No Cache"


def test_cache_cleanup_after_request(middleware):
    """Test that the cache is cleared after the request lifecycle."""

    request = HttpRequest()
    middleware(request)

    # and after the cache, the cache should be cleaned up
    assert local_cache.get("user_profile", "after") == "after"


@override_settings(BASEROW_USE_LOCAL_CACHE=False)
def test_cache_disabled():
    """
    Test that the cache does not store values when BASEROW_USE_LOCAL_CACHE is False.
    """

    assert local_cache.get("user_profile", lambda: "disabled") == "disabled"
    assert local_cache.get("user_profile") is None
