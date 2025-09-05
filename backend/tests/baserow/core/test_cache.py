from unittest.mock import Mock, patch

from django.core.cache import cache
from django.http import HttpRequest
from django.test import override_settings

import pytest

from baserow.core.cache import (
    GLOBAL_CACHE_VERSION,
    LocalCacheMiddleware,
    global_cache,
    local_cache,
)
from baserow.version import VERSION


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


@pytest.mark.parametrize(
    "key",
    [
        "foo",
        "foo_bar",
        "foo_bar_123",
    ],
)
def test_get_versioned_cache_key(key):
    result = global_cache._get_versioned_cache_key(key)
    assert result == f"{VERSION}_{GLOBAL_CACHE_VERSION}_{key}__version_0"


def test_global_update_with_literal_default_value():
    def callback(data):
        return data + " world"

    result = global_cache.update(
        key="my-key",
        callback=callback,
        default_value="hello",
    )

    assert result == "hello world"

    cached_value = global_cache.get("my-key")
    assert cached_value == "hello world"


def test_global_update_with_callable_default_value():
    def callback(data):
        data.append("bar")
        return data

    result = global_cache.update(
        key="my-key", callback=callback, default_value=lambda: [], timeout=60
    )

    assert result == ["bar"]


def test_global_update_with_existing_cache_value():
    global_cache.get("my-key", lambda: ["apple", "banana"])

    def callback(data):
        data.append("cherry")
        return data

    result = global_cache.update(
        key="my-key", callback=callback, default_value=lambda: [], timeout=60
    )

    assert result == ["apple", "banana", "cherry"]


def test_global_update_with_locking():
    def callback(data):
        return data

    mock_lock = Mock()
    mock_lock.acquire = Mock()
    mock_lock.release = Mock()

    with patch.object(cache, "lock", return_value=mock_lock) as mocked_lock:
        global_cache.update(
            key="my-key", callback=callback, default_value="foo", timeout=60
        )

        # Ensure the lock was acquired and released
        cache_key = global_cache._get_versioned_cache_key("my-key")
        mocked_lock.assert_called_once_with(f"{cache_key}__lock", timeout=10)
        mock_lock.acquire.assert_called_once_with()
        mock_lock.release.assert_called_once_with()


def test_global_update_lock_release_on_exception():
    def callback(data):
        raise ValueError("unexpected error")

    mock_lock = Mock()
    mock_lock.acquire = Mock()
    mock_lock.release = Mock()

    with patch.object(cache, "lock", return_value=mock_lock):
        with pytest.raises(ValueError):
            global_cache.update(
                key="my-key", callback=callback, default_value="foo", timeout=60
            )

        # Verify lock was still released
        mock_lock.release.assert_called_once_with()
