from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

from baserow.api.authentication import JSONWebTokenAuthentication
from baserow.core.user.cache import (
    get_cached_user,
    invalidate_cached_user,
    set_cached_user,
)
from baserow.core.user.handler import UserHandler

_CACHE_ON = override_settings(BASEROW_CACHE_TTL_SECONDS=30)
_CACHE_OFF = override_settings(BASEROW_CACHE_TTL_SECONDS=0)


@pytest.mark.django_db
@_CACHE_ON
def test_set_and_get_cached_user(data_fixture):
    user = data_fixture.create_user()

    assert get_cached_user(user.id) is None

    set_cached_user(user)

    cached = get_cached_user(user.id)
    assert cached is not None
    assert cached.id == user.id
    assert cached.is_active == user.is_active
    assert cached.profile.concurrency_limit == user.profile.concurrency_limit


@pytest.mark.django_db
@_CACHE_OFF
def test_caching_disabled_when_ttl_is_zero(data_fixture):
    user = data_fixture.create_user()

    set_cached_user(user)
    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_invalidate_cached_user(data_fixture):
    user = data_fixture.create_user()
    set_cached_user(user)
    assert get_cached_user(user.id) is not None

    invalidate_cached_user(user.id)
    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_user_save(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    set_cached_user(user)
    assert get_cached_user(user.id) is not None

    with django_capture_on_commit_callbacks(execute=True):
        user.first_name = "Changed"
        user.save()

    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_profile_save(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    set_cached_user(user)
    assert get_cached_user(user.id) is not None

    with django_capture_on_commit_callbacks(execute=True):
        user.profile.concurrency_limit = 5
        user.profile.save()

    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_deactivation(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    set_cached_user(user)

    with django_capture_on_commit_callbacks(execute=True):
        user.is_active = False
        user.save()

    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_signal_invalidates_cache_on_user_delete(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    set_cached_user(user)
    assert get_cached_user(user.id) is not None

    with django_capture_on_commit_callbacks(execute=True):
        user.delete()

    assert get_cached_user(user.id) is None


@pytest.mark.django_db
@_CACHE_ON
def test_cached_user_profile_accessible_without_extra_query(data_fixture):
    user = data_fixture.create_user()
    set_cached_user(user)

    cached = get_cached_user(user.id)

    with CaptureQueriesContext(connection) as ctx:
        _ = cached.profile.concurrency_limit
        _ = cached.profile.last_password_change
        _ = cached.is_active
        _ = cached.is_staff

    assert len(ctx.captured_queries) == 0


@pytest.mark.django_db
@_CACHE_ON
def test_cached_user_omits_password_hash(data_fixture):
    import pickle

    user = data_fixture.create_user(password="passwordhashcanary")
    invalidate_cached_user(user.id)
    token = AccessToken.for_user(user)

    JSONWebTokenAuthentication().get_user(token)

    cached = get_cached_user(user.id)
    assert cached is not None
    assert user.password.encode() not in pickle.dumps(cached)


@pytest.mark.django_db
@_CACHE_ON
def test_get_user_uses_cache_on_second_call(data_fixture):
    user = data_fixture.create_user()
    token = AccessToken.for_user(user)
    auth = JSONWebTokenAuthentication()

    # First call — cache miss, hits DB
    with CaptureQueriesContext(connection) as ctx1:
        result1 = auth.get_user(token)
    db_queries_first = len(ctx1.captured_queries)
    assert db_queries_first >= 1
    assert result1.id == user.id

    # Second call — cache hit, no DB
    with CaptureQueriesContext(connection) as ctx2:
        result2 = auth.get_user(token)
    assert len(ctx2.captured_queries) == 0
    assert result2.id == user.id


@pytest.mark.django_db
@_CACHE_OFF
def test_get_user_always_hits_db_when_cache_disabled(data_fixture):
    user = data_fixture.create_user()
    token = AccessToken.for_user(user)
    auth = JSONWebTokenAuthentication()

    with CaptureQueriesContext(connection) as ctx1:
        auth.get_user(token)
    first_count = len(ctx1.captured_queries)

    with CaptureQueriesContext(connection) as ctx2:
        auth.get_user(token)
    second_count = len(ctx2.captured_queries)

    assert first_count >= 1
    assert second_count >= 1


@pytest.mark.django_db
@_CACHE_ON
def test_password_change_invalidates_cache_and_rejects_old_token(
    data_fixture, api_request_factory, django_capture_on_commit_callbacks
):
    with freeze_time("2020-01-01 12:00:00"):
        user, token = data_fixture.create_user_and_token(password="oldpass")

    auth = JSONWebTokenAuthentication()

    # Warm the cache by making an authenticated request
    with freeze_time("2020-01-01 12:00:01"):
        request = api_request_factory.get(
            reverse("api:user:account"),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        authenticated_user, _ = auth.authenticate(request)
        assert authenticated_user.id == user.id
        assert get_cached_user(user.id) is not None

    # Change password — should invalidate cache
    with freeze_time("2020-01-01 12:00:02"):
        with django_capture_on_commit_callbacks(execute=True):
            UserHandler().change_password(user, "oldpass", "newpass123")
        assert get_cached_user(user.id) is None

    # Old token should be rejected (even after cache is re-populated)
    with freeze_time("2020-01-01 12:00:03"):
        request = api_request_factory.get(
            reverse("api:user:account"),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        with pytest.raises(AuthenticationFailed):
            auth.authenticate(request)


@pytest.mark.django_db
@_CACHE_ON
def test_user_delete_invalidates_cache_and_rejects_old_token(
    data_fixture, api_request_factory, django_capture_on_commit_callbacks
):
    with freeze_time("2020-01-01 12:00:00"):
        user, token = data_fixture.create_user_and_token(password="oldpass")

    auth = JSONWebTokenAuthentication()

    with freeze_time("2020-01-01 12:00:01"):
        request = api_request_factory.get(
            reverse("api:user:account"),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        authenticated_user, _ = auth.authenticate(request)
        assert authenticated_user.id == user.id
        assert get_cached_user(user.id) is not None

    with freeze_time("2020-01-01 12:00:02"):
        with django_capture_on_commit_callbacks(execute=True):
            user.delete()
        assert get_cached_user(user.id) is None

    with freeze_time("2020-01-01 12:00:03"):
        request = api_request_factory.get(
            reverse("api:user:account"),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        with pytest.raises(AuthenticationFailed):
            auth.authenticate(request)
