from django.core.cache import cache

import pytest

from baserow.celery_singleton_backend import SingletonAutoRescheduleFlag


@pytest.mark.django_db
def test_acquire_is_atomic_and_stores_token():
    flag = SingletonAutoRescheduleFlag("test_lock", timeout=60)

    assert flag.acquire("token-a") is True
    # Second acquire fails while held, value stays the first token.
    assert flag.acquire("token-b") is False
    assert cache.get("test_lock") == "token-a"


@pytest.mark.django_db
def test_clear_if_only_deletes_on_matching_token():
    flag = SingletonAutoRescheduleFlag("test_lock", timeout=60)
    flag.acquire("token-a")

    assert flag.clear_if("wrong-token") is False
    assert cache.get("test_lock") == "token-a"

    assert flag.clear_if("token-a") is True
    assert cache.get("test_lock") is None


@pytest.mark.django_db
def test_extend_if_extends_only_for_matching_token():
    flag = SingletonAutoRescheduleFlag("test_lock", timeout=60)

    # Nothing to extend yet.
    assert flag.extend_if("token-a") is False

    flag.acquire("token-a")
    # A different token no longer owns the lock: refuse to extend.
    assert flag.extend_if("token-b") is False
    # The owning token extends the TTL without overwriting the value.
    assert flag.extend_if("token-a") is True
    assert cache.get("test_lock") == "token-a"


@pytest.mark.django_db
def test_default_timeout_is_backwards_compatible(settings):
    flag = SingletonAutoRescheduleFlag("test_lock")
    assert flag.timeout == settings.AUTO_INDEX_LOCK_EXPIRY * 2


@pytest.mark.django_db
def test_default_timeout_follows_overridden_setting(settings):
    # Resolved in the body, so an overridden setting is honored (a default arg would
    # have frozen the value at import time).
    settings.AUTO_INDEX_LOCK_EXPIRY = 7
    flag = SingletonAutoRescheduleFlag("test_lock")
    assert flag.timeout == 14
