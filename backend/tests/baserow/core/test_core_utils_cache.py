from baserow.core.cache import GlobalCache


def test_local_cache_get_literally_stores_default():
    """If the cache is empty, a literal default value is stored and returned."""

    cache_key = "test_literal_default"

    result = GlobalCache().get(
        key=cache_key,
        default="my_default_value",
        timeout=6,
    )
    assert result == "my_default_value"


def test_local_cache_get_callable_stores_return_value():
    """
    If the cache is empty, a callable default's return value is stored and returned.
    """

    cache_key = "test_callable_default"

    def some_callable():
        return "callable_value"

    result = GlobalCache().get(
        key=cache_key,
        default=some_callable,
        timeout=6,
    )
    assert result == "callable_value"


def test_local_cache_get_uses_existing_value():
    """
    If the cache key already has a value, it should be returned without overwriting.
    """

    cache_key = "test_existing"

    result = GlobalCache().get(
        key=cache_key,
        default="existing_value",
        timeout=60,
    )

    result = GlobalCache().get(
        key=cache_key,
        default="unused_default",
        timeout=6,
    )

    assert result == "existing_value"


def test_versioned_cache_invalidation():
    """
    If a versioned key already exists, local_cache_get should retrieve
    that existing value rather than setting a new one.
    """

    base_key = "test_versioned_base2"

    result = GlobalCache().get(
        key=base_key,
        default="already_versioned",
        timeout=6,
    )

    GlobalCache().invalidate(base_key)

    result = GlobalCache().get(
        key=base_key,
        default="new_value",
        timeout=6,
    )

    assert result == "new_value"


def test_versioned_cache_invalidation_with_invalidation_key():
    """
    If a versioned key already exists, local_cache_get should retrieve
    that existing value rather than setting a new one.
    """

    base_key = "test_versioned_base3_"
    invalidate_key = "test_invalidate_key"

    result = GlobalCache().get(
        key=base_key + "1",
        invalidate_key=invalidate_key,
        default="already_versioned",
        timeout=6,
    )

    result = GlobalCache().get(
        key=base_key + "2",
        invalidate_key=invalidate_key,
        default="already_versioned",
        timeout=6,
    )

    GlobalCache().invalidate(invalidate_key=invalidate_key)

    result = GlobalCache().get(
        key=base_key + "1",
        invalidate_key=invalidate_key,
        default="new_value",
        timeout=6,
    )

    assert result == "new_value"

    result = GlobalCache().get(
        key=base_key + "2",
        invalidate_key=invalidate_key,
        default="new_value",
        timeout=6,
    )

    assert result == "new_value"
