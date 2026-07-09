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
def test_extend_preserves_value_and_reports_missing_key():
    flag = SingletonAutoRescheduleFlag("test_lock", timeout=60)

    # Nothing to extend yet.
    assert flag.extend() is False

    flag.acquire("token-a")
    assert flag.extend() is True
    # Extend must not overwrite the token.
    assert cache.get("test_lock") == "token-a"


@pytest.mark.django_db
def test_default_timeout_is_backwards_compatible(settings):
    flag = SingletonAutoRescheduleFlag("test_lock")
    assert flag.timeout == settings.AUTO_INDEX_LOCK_EXPIRY * 2
