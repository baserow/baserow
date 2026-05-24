from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.core.cache import (
    get_cached_settings,
    invalidate_cached_settings,
    set_cached_settings,
)
from baserow.core.handler import CoreHandler

_CACHE_ON = override_settings(BASEROW_CACHE_TTL_SECONDS=30)
_CACHE_OFF = override_settings(BASEROW_CACHE_TTL_SECONDS=0)


@pytest.mark.django_db
@_CACHE_ON
def test_set_and_get_cached_settings():
    instance = CoreHandler().get_settings()
    invalidate_cached_settings()

    assert get_cached_settings() is None

    set_cached_settings(instance)

    cached = get_cached_settings()
    assert cached is not None
    assert cached.pk == instance.pk
    assert cached.allow_new_signups == instance.allow_new_signups


@pytest.mark.django_db
@_CACHE_OFF
def test_caching_disabled_when_ttl_is_zero():
    instance = CoreHandler().get_settings()

    set_cached_settings(instance)
    assert get_cached_settings() is None


@pytest.mark.django_db
@_CACHE_ON
def test_invalidate_cached_settings():
    instance = CoreHandler().get_settings()
    set_cached_settings(instance)
    assert get_cached_settings() is not None

    invalidate_cached_settings()
    assert get_cached_settings() is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_settings_save(django_capture_on_commit_callbacks):
    instance = CoreHandler().get_settings()
    set_cached_settings(instance)
    assert get_cached_settings() is not None

    with django_capture_on_commit_callbacks(execute=True):
        instance.allow_new_signups = not instance.allow_new_signups
        instance.save()

    assert get_cached_settings() is None


@pytest.mark.django_db
@_CACHE_ON
def test_get_settings_uses_cache_on_second_call():
    CoreHandler().get_settings()
    invalidate_cached_settings()

    with CaptureQueriesContext(connection) as ctx1:
        CoreHandler().get_settings()
    assert len(ctx1.captured_queries) >= 1

    with CaptureQueriesContext(connection) as ctx2:
        CoreHandler().get_settings()
    assert len(ctx2.captured_queries) == 0


@pytest.mark.django_db
@_CACHE_OFF
def test_get_settings_always_hits_db_when_cache_disabled():
    CoreHandler().get_settings()

    with CaptureQueriesContext(connection) as ctx1:
        CoreHandler().get_settings()
    with CaptureQueriesContext(connection) as ctx2:
        CoreHandler().get_settings()

    assert len(ctx1.captured_queries) >= 1
    assert len(ctx2.captured_queries) >= 1
