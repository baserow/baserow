from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.contrib.database.api.tokens.authentications import TokenAuthentication
from baserow.contrib.database.tokens.cache import (
    _cache_key,
    cache,
    get_cached_token,
    invalidate_cached_token,
    set_cached_token,
)
from baserow.contrib.database.tokens.handler import TokenHandler

_CACHE_ON = override_settings(BASEROW_CACHE_TTL_SECONDS=30)
_CACHE_OFF = override_settings(BASEROW_CACHE_TTL_SECONDS=0)


@pytest.mark.django_db
@_CACHE_ON
def test_set_and_get_cached_token(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)

    assert get_cached_token(token.key) is None

    set_cached_token(token)

    cached = get_cached_token(token.key)
    assert cached is not None
    assert cached.id == token.id
    assert cached.user_id == user.id
    assert cached.workspace_id == workspace.id


@pytest.mark.django_db
@_CACHE_ON
def test_cached_token_omits_auth_secrets(data_fixture):
    import pickle

    user = data_fixture.create_user(password="passwordhashcanary")
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    invalidate_cached_token(token.key)

    TokenHandler().get_by_key(key=token.key)

    cached = cache.get(_cache_key(token.key))
    assert cached is not None
    payload = pickle.dumps(cached)
    assert token.key.encode() not in payload
    assert user.password.encode() not in payload


@pytest.mark.django_db
@_CACHE_OFF
def test_db_token_caching_disabled_when_ttl_is_zero(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)

    set_cached_token(token)
    assert get_cached_token(token.key) is None


@pytest.mark.django_db
@_CACHE_ON
def test_get_by_key_populates_cache_on_first_call(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    invalidate_cached_token(token.key)

    handler = TokenHandler()

    # First call — cache miss, hits DB
    with CaptureQueriesContext(connection) as ctx1:
        first = handler.get_by_key(key=token.key)
    assert first.id == token.id
    assert len(ctx1.captured_queries) >= 1

    # Second call — cache hit, no DB
    with CaptureQueriesContext(connection) as ctx2:
        second = handler.get_by_key(key=token.key)
    assert second.id == token.id
    assert len(ctx2.captured_queries) == 0


@pytest.mark.django_db
@_CACHE_ON
def test_token_http_request_runs_no_queries_after_cache_warmup(
    data_fixture, api_request_factory
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    invalidate_cached_token(token.key)

    auth = TokenAuthentication()

    def _make_request():
        return api_request_factory.get(
            "/api/database/rows/table/1/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

    # First request — cache miss, hits DB to resolve token + user + profile
    with CaptureQueriesContext(connection) as ctx1:
        authenticated_user, _ = auth.authenticate(_make_request())
    assert authenticated_user.id == user.id
    assert len(ctx1.captured_queries) >= 1

    # Subsequent requests — cache hit, full auth flow runs no queries
    for _ in range(3):
        with CaptureQueriesContext(connection) as ctx:
            authenticated_user, _ = auth.authenticate(_make_request())
        assert authenticated_user.id == user.id
        assert len(ctx.captured_queries) == 0, [q["sql"] for q in ctx.captured_queries]


@pytest.mark.django_db
@_CACHE_ON
def test_token_save_invalidates_cache(data_fixture, django_capture_on_commit_callbacks):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    set_cached_token(token)
    assert get_cached_token(token.key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        token.name = "Renamed"
        token.save()

    assert get_cached_token(token.key) is None


@pytest.mark.django_db
@_CACHE_ON
def test_token_delete_invalidates_cache(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    set_cached_token(token)
    assert get_cached_token(token.key) is not None

    cached_key = token.key
    with django_capture_on_commit_callbacks(execute=True):
        token.delete()

    assert get_cached_token(cached_key) is None


@pytest.mark.django_db
@_CACHE_ON
def test_rotate_token_key_invalidates_old_and_new_key(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    old_key = token.key
    set_cached_token(token)
    assert get_cached_token(old_key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        rotated = TokenHandler().rotate_token_key(user, token)

    assert rotated.key != old_key
    # The old key must no longer point to the stale cached token.
    assert get_cached_token(old_key) is None
    # The new key starts uncached; next get_by_key will re-populate it.
    assert get_cached_token(rotated.key) is None


@pytest.mark.django_db
@_CACHE_ON
def test_user_save_invalidates_token_cache(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    set_cached_token(token)
    assert get_cached_token(token.key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        user.first_name = "Changed"
        user.save()

    assert get_cached_token(token.key) is None


@pytest.mark.django_db
@_CACHE_ON
def test_user_profile_save_invalidates_token_cache(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    token = data_fixture.create_token(user=user, workspace=workspace)
    set_cached_token(token)
    assert get_cached_token(token.key) is not None

    with django_capture_on_commit_callbacks(execute=True):
        user.profile.concurrency_limit = 5
        user.profile.save()

    assert get_cached_token(token.key) is None
