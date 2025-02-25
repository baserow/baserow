from django.core.cache import cache

from baserow.core.utils import invalidate_versioned_cache, safe_get_or_set_cache


def test_safe_get_or_set_cache_literally_stores_default():
    """If the cache is empty, a literal default value is stored and returned."""

    cache_key = "test_literal_default"
    cache.delete(cache_key)

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default="my_default_value",
        timeout=60,
    )
    assert result == "my_default_value"
    assert cache.get(cache_key) == "my_default_value"


def test_safe_get_or_set_cache_callable_stores_return_value():
    """
    If the cache is empty, a callable default's return value is stored and returned.
    """

    cache_key = "test_callable_default"
    cache.delete(cache_key)

    def some_callable():
        return "callable_value"

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default=some_callable,
        timeout=60,
    )
    assert result == "callable_value"
    assert cache.get(cache_key) == "callable_value"


def test_safe_get_or_set_cache_uses_existing_value():
    """
    If the cache key already has a value, it should be returned without overwriting.
    """

    cache_key = "test_existing"
    cache.delete(cache_key)
    cache.set(cache_key, "existing_value", 60)

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default="unused_default",
        timeout=60,
    )
    assert result == "existing_value"
    # Confirm it didn't overwrite with 'unused_default'
    assert cache.get(cache_key) == "existing_value"


def test_versioned_cache_set_and_retrieve():
    """
    When a version_cache_key is given and the value does not exist,
    it should store and retrieve the value under <cache_key>__version_X.
    """

    base_key = "test_versioned_base"
    version_cache_key = "test_versioned_key"
    cache.delete(base_key)
    cache.delete(version_cache_key)

    # No version exists, so this should initialize version=0
    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="versioned_value",
        timeout=60,
    )
    assert result == "versioned_value"
    # Confirm the value is stored under the versioned key
    assert cache.get(f"{base_key}__version_0") == "versioned_value"


def test_versioned_cache_hit():
    """
    If a versioned key already exists, safe_get_or_set_cache should retrieve
    that existing value rather than setting a new one.
    """

    base_key = "test_versioned_base2"
    version_cache_key = "test_versioned_key2"
    cache.delete(base_key)
    cache.delete(version_cache_key)

    # Manually set version=5
    cache.set(version_cache_key, 5)
    full_key = f"{base_key}__version_5"
    cache.set(full_key, "already_versioned", 60)

    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="unused_default",
        timeout=60,
    )
    assert result == "already_versioned"
    assert cache.get(full_key) == "already_versioned"


def test_invalidate_versioned_cache_increments_existing():
    """
    If a version_cache_key already exists, calling invalidate_versioned_cache should
    increment the version.
    """

    version_key = "test_invalidate_existing"
    cache.set(version_key, 3)

    invalidate_versioned_cache(version_key)
    assert cache.get(version_key) == 4


def test_invalidate_versioned_cache_sets_new_if_absent():
    """
    If a versioned cache key doesn't exist, calling invalidate_versioned_cache should
    create it and set it to 1.
    """

    version_key = "test_invalidate_absent"
    cache.delete(version_key)

    invalidate_versioned_cache(version_key)
    assert cache.get(version_key) == 1
