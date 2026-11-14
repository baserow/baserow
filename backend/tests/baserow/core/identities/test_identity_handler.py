from datetime import datetime, timezone

from django.core.cache import cache

import pytest
from freezegun import freeze_time

from baserow.core.cache import global_cache
from baserow.core.identities.handler import (
    IDENTITY_LAST_ACTIVE_CACHE_KEY,
    IDENTITY_LAST_ACTIVE_CACHE_TTL_SECONDS,
    IdentityHandler,
)


@pytest.mark.django_db
def test_update_last_active(data_fixture):
    cache.clear()
    identity = data_fixture.create_identity(name="Writer")

    updated_identity = IdentityHandler().update_last_active(identity)

    assert updated_identity is identity
    assert identity.profile.last_active is not None
    last_active = identity.profile.last_active
    identity.profile.refresh_from_db()
    assert identity.profile.last_active == last_active


@pytest.mark.django_db
def test_update_last_active_is_throttled_until_cache_expires(data_fixture):
    identity = data_fixture.create_identity(name="Writer")
    cache.clear()

    first_activity = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    with freeze_time(first_activity):
        IdentityHandler().update_last_active(identity)

    with freeze_time("2026-01-01 12:00:59"):
        IdentityHandler().update_last_active(identity)

    identity.profile.refresh_from_db()
    assert identity.profile.last_active == first_activity

    global_cache.invalidate(
        IDENTITY_LAST_ACTIVE_CACHE_KEY.format(identity_id=identity.id),
    )

    second_activity = datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)
    with freeze_time(second_activity):
        IdentityHandler().update_last_active(identity)

    identity.profile.refresh_from_db()
    assert identity.profile.last_active == second_activity
    assert IDENTITY_LAST_ACTIVE_CACHE_TTL_SECONDS == 60
