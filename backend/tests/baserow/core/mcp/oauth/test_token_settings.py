from datetime import timedelta

from django.conf import settings
from django.utils import timezone

import pytest
from freezegun import freeze_time
from oauth2_provider.models import AccessToken, RefreshToken

from tests.baserow.core.mcp.oauth.helpers import (
    obtain_tokens,
)


def _refresh(client, tokens):
    return client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
        },
    )


@pytest.mark.django_db
def test_tokens_are_stored_hashed(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)

    stored = AccessToken.objects.get(user=user)
    assert stored.token != tokens["access_token"]


@pytest.mark.django_db
def test_replayed_refresh_token_revokes_the_family(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )

    rotated = _refresh(client, tokens)
    assert rotated.status_code == 200
    assert _refresh(client, tokens).status_code == 400
    # The replay revoked the rotated token too.
    new_tokens = {**rotated.json(), "client_id": tokens["client_id"]}
    assert _refresh(client, new_tokens).status_code == 400


@pytest.mark.django_db
def test_refresh_token_works_after_29_days(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )
    with freeze_time(timezone.now() + timedelta(days=29)):
        assert _refresh(client, tokens).status_code == 200


@pytest.mark.django_db
def test_refresh_token_expires_after_30_days(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )
    with freeze_time(timezone.now() + timedelta(days=31)):
        response = _refresh(client, tokens)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


@pytest.mark.django_db
def test_offline_access_is_kept_in_the_token_scope(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )
    assert "offline_access" in tokens["scope"].split()
    assert "mcp" in tokens["scope"].split()


@pytest.mark.django_db
def test_offline_access_is_not_added_unless_requested(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    assert "offline_access" not in tokens["scope"].split()


@pytest.mark.django_db
def test_no_refresh_token_without_offline_access(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    assert "refresh_token" not in tokens
    assert not RefreshToken.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_offline_access_issues_a_working_refresh_token(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )
    assert tokens["refresh_token"]
    assert RefreshToken.objects.filter(user=user).count() == 1

    response = _refresh(client, tokens)
    assert response.status_code == 200, response.content
    assert response.json()["refresh_token"]


def test_cimd_allowlist_defaults_to_any_host():
    assert settings.OAUTH2_PROVIDER["CIMD_ALLOWED_HOSTS"] == ["*"]
