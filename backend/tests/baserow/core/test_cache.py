from django.http import HttpRequest

import pytest

from baserow.core.cache import ShortCacheMiddleware, get_short_cache


# Simulate a Django view
def mock_view(request):
    user_profile = get_short_cache(
        "user_profile", lambda: {"id": 1, "name": "Test User"}
    )
    return user_profile


@pytest.fixture
def middleware():
    """Provide an instance of the middleware."""

    return ShortCacheMiddleware(get_response=mock_view)


def test_cache_storage(middleware):
    """Test that the cache stores and retrieves values correctly."""

    request = HttpRequest()
    response = middleware(request)

    assert response == {"id": 1, "name": "Test User"}

    # Test that the value is cached
    cached_value = get_short_cache("user_profile")
    assert cached_value is None


def test_callable_default():
    """Test that callable defaults are executed and cached."""

    # Check if the callable default was executed
    assert get_short_cache("user_profile", lambda: "test") == "test"


def test_cache_isolation(middleware):
    """Test that the cache is isolated between simulated requests."""

    get_short_cache("user_profile", "before")

    request1 = HttpRequest()
    result = middleware(request1)

    assert result == {"id": 1, "name": "Test User"}
    assert get_short_cache("user_profile", "No Cache") == "No Cache"

    # Simulate a new request and ensure the cache is isolated
    request2 = HttpRequest()
    middleware(request2)

    # Ensure the second request starts with an empty cache
    assert get_short_cache("user_profile", "No Cache") == "No Cache"


def test_cache_cleanup(middleware):
    """Test that the cache is cleared after the request lifecycle."""

    request = HttpRequest()
    middleware(request)

    # After the request, the cache should be cleaned
    assert get_short_cache("user_profile", "Empty") == "Empty"
