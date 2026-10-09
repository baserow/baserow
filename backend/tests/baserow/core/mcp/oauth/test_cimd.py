from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from oauth2_provider.models import Application

from tests.baserow.core.mcp.oauth.helpers import authorize_query, pkce_pair

CLAUDE_CLIENT = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_REDIRECT = "https://claude.ai/api/mcp/auth_callback"
EVIL_CLIENT = "https://evil.example/client.json"
EVIL_REDIRECT = "https://evil.example/cb"
FETCH = "oauth2_provider.cimd.SafeMetadataFetcher.fetch"


def _metadata(client_id, redirect_uri):
    return {
        "client_id": client_id,
        "client_name": "Claude",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


@pytest.mark.django_db
def test_cimd_allowlisted_host_reaches_consent(client):
    _, challenge = pkce_pair()
    with patch(FETCH, return_value=(_metadata(CLAUDE_CLIENT, CLAUDE_REDIRECT), 300)):
        query = authorize_query(CLAUDE_CLIENT, challenge, redirect_uri=CLAUDE_REDIRECT)
        response = client.get(f"/oauth/authorize/?{query}")

    assert response.status_code == 302
    assert "/mcp-authorize" in response["Location"]
    application = Application.objects.get(client_id=CLAUDE_CLIENT)
    assert application.redirect_uris == CLAUDE_REDIRECT


@pytest.mark.django_db
def test_cimd_other_host_is_rejected(client, settings):
    settings.OAUTH2_PROVIDER = {
        **settings.OAUTH2_PROVIDER,
        "CIMD_ALLOWED_HOSTS": ["claude.ai", ".chatgpt.com"],
    }
    _, challenge = pkce_pair()
    with patch(
        FETCH, return_value=(_metadata(EVIL_CLIENT, EVIL_REDIRECT), 300)
    ) as fetch:
        query = authorize_query(EVIL_CLIENT, challenge, redirect_uri=EVIL_REDIRECT)
        response = client.get(f"/oauth/authorize/?{query}")

    fetch.assert_not_called()
    # Re-adding the server wouldn't help, so the re-add hint isn't shown.
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith(f"{settings.PUBLIC_WEB_FRONTEND_URL}/mcp-authorize?")
    assert parse_qs(urlparse(location).query) == {"error": ["invalid_request"]}
    assert EVIL_REDIRECT not in location
    assert "code=" not in location
    assert not Application.objects.filter(client_id=EVIL_CLIENT).exists()
