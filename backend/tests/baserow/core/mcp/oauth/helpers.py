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


_cimd_documents = {}


def fake_cimd_fetch(_fetcher, client_id):
    """Stands in for the HTTP fetch of a client metadata document."""

    return _cimd_documents[client_id], 300


def cimd_client(client, redirect_uri=REDIRECT_URI, client_name="Test MCP client"):
    """
    Returns the client_id of a new CIMD client on an allowlisted host. The metadata
    document is served by the `cimd_fetch` fixture's patched fetcher.
    """

    client_id = f"https://claude.ai/oauth/test-client-{secrets.token_hex(6)}.json"
    _cimd_documents[client_id] = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    return client_id


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


def enabled_tool_names():
    from baserow.core.mcp.registries import mcp_tool_registry

    return [tool.name for tool in mcp_tool_registry.get_enabled_tools()]


def obtain_tokens(client, api_client, token, workspace, tools=None, client_id=None):
    """
    Runs consent -> token. `token` is the user's JWT, `tools=None` grants
    every enabled tool, `client_id=None` uses a new CIMD client. The result
    carries the `endpoint_id` consent picked.
    """

    verifier, challenge = pkce_pair()
    client_id = client_id or cimd_client(client)
    query = authorize_query(client_id, challenge)
    response = api_client.post(
        reverse("api:mcp:oauth_consent"),
        {
            "query": query,
            "allow": True,
            "workspace_id": workspace.id,
            "tools": enabled_tool_names() if tools is None else tools,
        },
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
    tokens = response.json()
    endpoint_id = int(tokens["scope"].split("endpoint:")[1].split()[0])
    return {**tokens, "client_id": client_id, "endpoint_id": endpoint_id}
