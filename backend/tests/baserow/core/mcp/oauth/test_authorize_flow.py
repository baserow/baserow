import hashlib
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.urls import reverse

import pytest
from oauth2_provider.models import AccessToken

from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    obtain_tokens,
    pkce_pair,
    register_dcr_client,
)


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
    assert location.path == "/mcp/authorize"
    assert parse_qs(location.query)["client_id"] == [client_id]


@pytest.mark.django_db
def test_authorize_without_pkce_is_rejected(client):
    client_id = register_dcr_client(client)
    query = authorize_query(client_id, "x").replace("code_challenge=x", "")
    response = client.get(f"/oauth/authorize/?{query}")
    # oauthlib treats a missing code challenge as fatal: shown, never redirected.
    assert response.status_code == 400
    assert "Location" not in response


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
