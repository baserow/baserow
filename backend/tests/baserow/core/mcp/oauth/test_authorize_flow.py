import base64
import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.urls import reverse

import pytest
from oauth2_provider.models import AccessToken

from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    obtain_tokens,
    pkce_pair,
    register_dcr_client,
)

ISSUER = settings.OAUTH2_PROVIDER["OIDC_ISS_ENDPOINT"]


def post_consent(api_client, token, body):
    return api_client.post(
        reverse("api:mcp:oauth_consent"),
        body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_authorize_redirects_to_frontend_consent(client):
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge)
    response = client.get(f"/oauth/authorize/?{query}")
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert response["Location"].startswith(settings.PUBLIC_WEB_FRONTEND_URL)
    assert location.path == "/mcp-authorize"
    # The query travels base64url-encoded, unpadded, so the login round trip
    # (encodeURI + router) can't re-encode it.
    params = parse_qs(location.query)
    assert list(params) == ["request"]
    encoded = params["request"][0]
    assert re.fullmatch(r"[A-Za-z0-9_-]+", encoded)
    padded = encoded + "=" * (-len(encoded) % 4)
    assert base64.urlsafe_b64decode(padded).decode() == query


def without_param(query, name):
    params = parse_qs(query)
    params.pop(name)
    return urlencode(params, doseq=True)


def assert_redirects_with_error(response, error):
    assert response.status_code == 302
    assert response["Location"].startswith(REDIRECT_URI)
    assert "/mcp-authorize" not in response["Location"]
    query = parse_qs(urlparse(response["Location"]).query)
    assert query["error"] == [error]
    assert query["state"] == ["s1"]
    assert query["iss"] == [ISSUER]


@pytest.mark.django_db
def test_authorize_without_pkce_is_rejected(client):
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "code_challenge")
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_request")


@pytest.mark.django_db
def test_authorize_rejects_plain_challenge_method(client):
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge).replace("S256", "plain")
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_request")


@pytest.mark.django_db
def test_authorize_rejects_foreign_resource(client):
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge) + "&resource=https%3A%2F%2Fevil.test"
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_target")


@pytest.mark.django_db
def test_consent_post_rejects_plain_challenge_method(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge).replace("S256", "plain")
    response = post_consent(
        api_client,
        token,
        {"query": query, "endpoint_id": endpoint.id, "allow": True},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@pytest.mark.django_db
def test_consent_post_rejects_foreign_resource(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge) + "&resource=https%3A%2F%2Fevil.test"
    response = post_consent(
        api_client,
        token,
        {"query": query, "endpoint_id": endpoint.id, "allow": True},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_target"


@pytest.mark.django_db
def test_consent_get_without_redirect_uri_uses_registered_one(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "redirect_uri")
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": query},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json()["redirect_host"] == "127.0.0.1"


@pytest.mark.django_db
def test_missing_resource_is_pinned_to_mcp_resource(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    client_id = register_dcr_client(client)
    verifier, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "resource")
    response = post_consent(
        api_client,
        token,
        {"query": query, "endpoint_id": endpoint.id, "allow": True},
    )
    assert response.status_code == 200
    code = parse_qs(urlparse(response.json()["redirect_url"]).query)["code"][0]
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert response.status_code == 200, response.content
    checksum = hashlib.sha256(response.json()["access_token"].encode()).hexdigest()
    access = AccessToken.objects.get(token_checksum=checksum)
    assert access.allows_audience(settings.MCP_RESOURCE_URL)


@pytest.mark.django_db
def test_authorize_unknown_client_is_not_redirected(client):
    _, challenge = pkce_pair()
    response = client.get(f"/oauth/authorize/?{authorize_query('nope', challenge)}")
    assert response.status_code == 400


@pytest.mark.django_db
def test_consent_get_lists_user_endpoints(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    data_fixture.create_mcp_endpoint()
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_name"] == "Test MCP client"
    assert data["client_id"] == client_id
    assert data["redirect_host"] == "127.0.0.1"
    assert [e["id"] for e in data["endpoints"]] == [endpoint.id]


@pytest.mark.django_db
def test_consent_get_invalid_query(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": "client_id=nope"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_full_flow_issues_endpoint_bound_token(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    tokens = obtain_tokens(client, api_client, token, endpoint)
    checksum = hashlib.sha256(tokens["access_token"].encode()).hexdigest()
    access = AccessToken.objects.get(token_checksum=checksum)
    assert set(access.scope.split()) == {"mcp", f"endpoint:{endpoint.id}"}
    assert access.user_id == user.id
    assert access.allows_audience(settings.MCP_RESOURCE_URL)
    assert tokens["refresh_token"]


@pytest.mark.django_db
def test_consent_rejects_foreign_endpoint(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    foreign = data_fixture.create_mcp_endpoint(user=other, workspace=workspace)
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        {
            "query": authorize_query(client_id, challenge),
            "endpoint_id": foreign.id,
            "allow": True,
        },
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_consent_deny_returns_access_denied(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        {"query": authorize_query(client_id, challenge), "allow": False},
    )
    assert response.status_code == 200
    redirect_url = response.json()["redirect_url"]
    assert redirect_url.startswith("http://127.0.0.1:33418/callback")
    query = parse_qs(urlparse(redirect_url).query)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["s1"]
    assert query["iss"] == [ISSUER]


@pytest.mark.django_db
def test_consent_can_create_endpoint(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        {
            "query": authorize_query(client_id, challenge),
            "new_endpoint": {"name": "Claude", "workspace_id": workspace.id},
            "allow": True,
        },
    )
    assert response.status_code == 200
    assert "code=" in response.json()["redirect_url"]
    assert MCPEndpoint.objects.filter(user=user, name="Claude").exists()


@pytest.mark.django_db
def test_consent_cannot_create_endpoint_in_foreign_workspace(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    foreign_workspace = data_fixture.create_workspace()
    client_id = register_dcr_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        {
            "query": authorize_query(client_id, challenge),
            "new_endpoint": {"name": "Claude", "workspace_id": foreign_workspace.id},
            "allow": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_invalid_query_does_not_create_endpoint(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    response = post_consent(
        api_client,
        token,
        {
            "query": "client_id=nope",
            "new_endpoint": {"name": "Claude", "workspace_id": workspace.id},
            "allow": True,
        },
    )
    assert response.status_code == 400
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_requires_authentication(api_client):
    response = api_client.get(reverse("api:mcp:oauth_consent"))
    assert response.status_code == 401
