import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.urls import reverse

REDIRECT_URI = "http://127.0.0.1:33418/callback"


def pkce_pair():
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def register_dcr_client(client, redirect_uri=REDIRECT_URI):
    response = client.post(
        "/oauth/register/",
        {
            "client_name": "Test MCP client",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    return response.json()["client_id"]


def authorize_query(client_id, challenge, redirect_uri=REDIRECT_URI, state="s1"):
    return urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp",
            "state": state,
            "resource": settings.MCP_RESOURCE_URL,
        }
    )


def obtain_tokens(client, api_client, token, endpoint):
    """Runs DCR -> consent -> token. `token` is the user's JWT."""

    verifier, challenge = pkce_pair()
    client_id = register_dcr_client(client)
    query = authorize_query(client_id, challenge)
    response = api_client.post(
        reverse("api:mcp:oauth_consent"),
        {"query": query, "endpoint_id": endpoint.id, "allow": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    redirect = urlparse(response.json()["redirect_url"])
    code = parse_qs(redirect.query)["code"][0]
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert response.status_code == 200, response.content
    return {**response.json(), "client_id": client_id}
