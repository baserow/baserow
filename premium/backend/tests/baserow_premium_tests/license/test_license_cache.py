from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from freezegun import freeze_time

from baserow_premium.license.cache import (
    get_cached_instance_wide_licenses,
    invalidate_cached_instance_wide_licenses,
    set_cached_instance_wide_licenses,
)
from baserow_premium.license.models import License
from baserow_premium.license.plugin import LicensePlugin

VALID_ONE_SEAT_LICENSE = (
    # valid_through: 2021-09-29T19:52:57.842696 UTC
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.e33Z4CxLSmD-R55Es24P3mR"
    b"8Oqn3LpaXvgYLzF63oFHat3paon7IBjBmOX3eyd8KjirVf3empJds4uUw2Nn2m7TVvRAtJ8XzNl-8ytf"
    b"2RLtmjMx1Xkgp5VZ8S7UqJ_cKLyl76eVRtGEA1DH2HdPKu1vBPJ4bzDfnhDPYl4k5z9XSSgqAbQ9WO0U"
    b"5kiI3BYjVRZSKnZMeguAGZ47ezDj_WArGcHAB8Pa2v3HFp5Y34DMJ8r3_hD5hxCKgoNx4AHx1Q-hRDqp"
    b"Aroj-4jl7KWvlP-OJNc1BgH2wnhFmeKHotv-Iumi83JQohyceUbG6j8rDDQvJfcn0W2_ebmUH3TKr-w="
    b"="
)

_CACHE_ON = override_settings(BASEROW_CACHE_TTL_SECONDS=30, DEBUG=True)
_CACHE_OFF = override_settings(BASEROW_CACHE_TTL_SECONDS=0, DEBUG=True)


@pytest.mark.django_db
@_CACHE_ON
def test_set_and_get_cached_instance_wide_licenses():
    license = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    invalidate_cached_instance_wide_licenses()
    assert get_cached_instance_wide_licenses() is None

    set_cached_instance_wide_licenses([license])

    cached = get_cached_instance_wide_licenses()
    assert cached is not None
    assert len(cached) == 1
    assert cached[0].pk == license.pk


@pytest.mark.django_db
@_CACHE_OFF
def test_caching_disabled_when_ttl_is_zero():
    license = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())

    set_cached_instance_wide_licenses([license])
    assert get_cached_instance_wide_licenses() is None


@pytest.mark.django_db
@_CACHE_ON
def test_invalidate_cached_instance_wide_licenses():
    license = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    set_cached_instance_wide_licenses([license])
    assert get_cached_instance_wide_licenses() is not None

    invalidate_cached_instance_wide_licenses()
    assert get_cached_instance_wide_licenses() is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_license_save(django_capture_on_commit_callbacks):
    license = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    set_cached_instance_wide_licenses([license])
    assert get_cached_instance_wide_licenses() is not None

    with django_capture_on_commit_callbacks(execute=True):
        license.save()

    assert get_cached_instance_wide_licenses() is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_license_delete(django_capture_on_commit_callbacks):
    license = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    set_cached_instance_wide_licenses([license])
    assert get_cached_instance_wide_licenses() is not None

    with django_capture_on_commit_callbacks(execute=True):
        license.delete()

    assert get_cached_instance_wide_licenses() is None


@pytest.mark.django_db
@_CACHE_ON
def test_cache_ttl_capped_at_earliest_license_expiry(mocker):
    # VALID_ONE_SEAT_LICENSE expires at 2021-09-29T19:52:57 UTC. Freezing time
    # 17s before expiry should cap the TTL below the 30s setting.
    license = License(license=VALID_ONE_SEAT_LICENSE.decode())
    mock_set = mocker.patch("baserow_premium.license.cache.cache.set")

    with freeze_time("2021-09-29 19:52:40"):
        set_cached_instance_wide_licenses([license])

    assert mock_set.called
    timeout = mock_set.call_args.kwargs["timeout"]
    assert 0 < timeout <= 17


@pytest.mark.django_db
@_CACHE_ON
def test_plugin_uses_shared_cache_for_user_none():
    # Seed the cache directly so the plugin must consult it and skip the DB.
    set_cached_instance_wide_licenses([])
    plugin = LicensePlugin()

    with CaptureQueriesContext(connection) as ctx:
        result = list(plugin._get_active_instance_wide_licenses(user_id=None))

    assert result == []
    assert len(ctx.captured_queries) == 0


@pytest.mark.django_db
@_CACHE_ON
def test_plugin_with_user_id_bypasses_shared_cache(data_fixture):
    user = data_fixture.create_user()
    set_cached_instance_wide_licenses([])
    plugin = LicensePlugin()

    # A specific user must not be served by the shared (user=None) cache —
    # the per-user query should still fire.
    with CaptureQueriesContext(connection) as ctx:
        list(plugin._get_active_instance_wide_licenses(user_id=user.id))

    assert len(ctx.captured_queries) >= 1
