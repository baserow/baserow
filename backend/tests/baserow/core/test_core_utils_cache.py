from baserow.core.utils import invalidate_versioned_cache, safe_get_or_set_cache


def test_safe_get_or_set_cache_literally_stores_default():
    """If the cache is empty, a literal default value is stored and returned."""

    cache_key = "test_literal_default"

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default="my_default_value",
        timeout=6,
    )
    assert result == "my_default_value"


def test_safe_get_or_set_cache_callable_stores_return_value():
    """
    If the cache is empty, a callable default's return value is stored and returned.
    """

    cache_key = "test_callable_default"

    def some_callable():
        return "callable_value"

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default=some_callable,
        timeout=6,
    )
    assert result == "callable_value"


def test_safe_get_or_set_cache_uses_existing_value():
    """
    If the cache key already has a value, it should be returned without overwriting.
    """

    cache_key = "test_existing"

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default="existing_value",
        timeout=60,
    )

    result = safe_get_or_set_cache(
        cache_key=cache_key,
        default="unused_default",
        timeout=6,
    )

    assert result == "existing_value"


def test_versioned_cache_set_and_retrieve():
    """
    When a version_cache_key is given and the value does not exist,
    it should store and retrieve the value under <cache_key>__version_X.
    """

    base_key = "test_versioned_base"
    version_cache_key = "test_versioned_key"

    # No version exists, so this should initialize version=0
    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="versioned_value",
        timeout=6,
    )
    assert result == "versioned_value"


def test_versioned_cache_hit():
    """
    If a versioned key already exists, safe_get_or_set_cache should retrieve
    that existing value rather than setting a new one.
    """

    base_key = "test_versioned_base2"
    version_cache_key = "test_versioned_key2"

    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="already_versioned",
        timeout=6,
    )

    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="unused_default",
        timeout=6,
    )

    assert result == "already_versioned"


def test_versioned_cache_invalidation():
    """
    If a versioned key already exists, safe_get_or_set_cache should retrieve
    that existing value rather than setting a new one.
    """

    base_key = "test_versioned_base2"
    version_cache_key = "test_versioned_key2"

    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="already_versioned",
        timeout=6,
    )

    invalidate_versioned_cache(version_cache_key)

    result = safe_get_or_set_cache(
        cache_key=base_key,
        version_cache_key=version_cache_key,
        default="new_value",
        timeout=6,
    )

    assert result == "new_value"
