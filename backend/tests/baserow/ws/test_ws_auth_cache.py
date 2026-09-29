from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.test.utils import override_settings

import pytest

from baserow.core.user.cache import invalidate_cached_user, set_cached_user
from baserow.ws.auth import get_user

User = get_user_model()

_CACHE_ON = override_settings(BASEROW_CACHE_TTL_SECONDS=30)
_CACHE_OFF = override_settings(BASEROW_CACHE_TTL_SECONDS=0)


def warm_cache(user):
    """Cache the user the way the HTTP authentication path does."""

    set_cached_user(
        User.objects.select_related("profile").defer("password").get(pk=user.pk)
    )


def forbid_executor(monkeypatch):
    """Every executor submission funnels through _run_sync."""

    def fail(*args, **kwargs):
        raise AssertionError("cached authentication must not submit to an executor")

    monkeypatch.setattr("baserow.ws.telemetry._run_sync", fail)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_cached_user_authenticates_without_any_executor(
    data_fixture, monkeypatch
):
    user, token = data_fixture.create_user_and_token()
    warm_cache(user)

    forbid_executor(monkeypatch)

    authenticated = await get_user(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_cache_miss_falls_back_to_the_database(data_fixture):
    user, token = data_fixture.create_user_and_token()
    invalidate_cached_user(user.id)

    authenticated = await get_user(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_OFF
async def test_authentication_still_works_when_the_cache_is_disabled(data_fixture):
    user, token = data_fixture.create_user_and_token()

    authenticated = await get_user(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_token_issued_before_the_last_password_change_is_rejected(data_fixture):
    user, token = data_fixture.create_user_and_token()
    user.profile.last_password_change = datetime.now(tz=timezone.utc) + timedelta(
        minutes=5
    )
    user.profile.save()
    warm_cache(user)

    assert await get_user(token) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_user_scheduled_for_deletion_is_rejected(data_fixture):
    user, token = data_fixture.create_user_and_token()
    user.profile.to_be_deleted = True
    user.profile.save()
    warm_cache(user)

    assert await get_user(token) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_deactivated_user_is_rejected(data_fixture):
    user, token = data_fixture.create_user_and_token()
    user.is_active = False
    user.save()
    warm_cache(user)

    assert await get_user(token) is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_a_rejecting_cache_entry_never_denies_a_valid_user(data_fixture):
    """The database stays authoritative, so a stale negative must not lock anyone out."""

    user, token = data_fixture.create_user_and_token()
    stale = User.objects.select_related("profile").defer("password").get(pk=user.pk)
    stale.is_active = False
    set_cached_user(stale)

    authenticated = await get_user(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_cached_user_without_a_preloaded_profile_falls_back(data_fixture):
    """Reading an unloaded profile would hit the database from the event loop."""

    user, token = data_fixture.create_user_and_token()
    set_cached_user(User.objects.defer("password").get(pk=user.pk))

    authenticated = await get_user(token)

    assert authenticated is not None
    assert authenticated.id == user.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@_CACHE_ON
async def test_invalid_token_is_rejected(data_fixture):
    data_fixture.create_user_and_token()

    assert await get_user("not-a-token") is None
