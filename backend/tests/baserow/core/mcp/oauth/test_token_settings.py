from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.utils import timezone

import pytest
from freezegun import freeze_time
from oauth2_provider.models import AccessToken
from rest_framework.reverse import reverse

from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
    pkce_pair,
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
    tokens = obtain_tokens(client, api_client, token, workspace)

    rotated = _refresh(client, tokens)
    assert rotated.status_code == 200
    assert _refresh(client, tokens).status_code == 400
    # The replay revoked the rotated token too.
    new_tokens = {**rotated.json(), "client_id": tokens["client_id"]}
    assert _refresh(client, new_tokens).status_code == 400


@pytest.mark.django_db
def test_refresh_token_expires_after_30_days(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    with freeze_time(timezone.now() + timedelta(days=31)):
        assert _refresh(client, tokens).status_code == 400


@pytest.mark.django_db
def test_offline_access_is_accepted(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    _, challenge = pkce_pair()
    query = authorize_query(cimd_client(client), challenge).replace(
        "scope=mcp", "scope=mcp+offline_access"
    )
    response = api_client.post(
        reverse("api:mcp:oauth_consent"),
        {
            "query": query,
            "allow": True,
            "workspace_id": workspace.id,
            "tools": enabled_tool_names(),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    assert "code" in parse_qs(urlparse(response.json()["redirect_url"]).query)


def test_cimd_allowlist_defaults_to_any_host():
    assert settings.OAUTH2_PROVIDER["CIMD_ALLOWED_HOSTS"] == ["*"]
