from urllib.parse import parse_qs, urlparse

from django.conf import settings

import pytest
from oauth2_provider.models import AccessToken, Application

from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    cimd_client,
    obtain_tokens,
    pkce_pair,
)


@pytest.mark.django_db
def test_password_grant_is_refused(client, data_fixture):
    # An application created in the admin may allow the password grant; the token
    # endpoint must still refuse it.
    user = data_fixture.create_user(email="victim@example.com", password="password")
    endpoint = data_fixture.create_mcp_endpoint(user=user)
    application = Application.objects.create(
        name="legacy",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_PASSWORD,
    )
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "password",
            "username": "victim@example.com",
            "password": "password",
            "client_id": application.client_id,
            "scope": f"mcp endpoint:{endpoint.id}",
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert response.status_code in (400, 401), response.content
    assert "access_token" not in response.json()
    assert not AccessToken.objects.filter(application=application).exists()


@pytest.mark.django_db
def test_client_credentials_cannot_get_endpoint_token(client, data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    application = Application(
        name="machine",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        client_secret="secret",
    )
    application.save()
    for scope in [f"mcp endpoint:{endpoint.id}", "mcp"]:
        response = client.post(
            "/oauth/token/",
            {
                "grant_type": "client_credentials",
                "client_id": application.client_id,
                "client_secret": "secret",
                "scope": scope,
            },
        )
        assert response.status_code in (400, 401), response.content
    assert not AccessToken.objects.filter(application=application).exists()


@pytest.mark.django_db
def test_implicit_response_type_is_refused(client):
    application = Application.objects.create(
        name="implicit",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_IMPLICIT,
        redirect_uris=REDIRECT_URI,
    )
    _, challenge = pkce_pair()
    query = authorize_query(application.client_id, challenge).replace(
        "response_type=code", "response_type=token"
    )
    response = client.get(f"/oauth/authorize/?{query}")
    location = response.get("Location", "")
    assert "/mcp-authorize" not in location
    assert "access_token" not in location


@pytest.mark.django_db
@pytest.mark.parametrize("extra", ["", "&mcp_endpoint_consent=True"])
def test_authorize_rejects_client_requested_endpoint_scope(client, extra):
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = (
        authorize_query(client_id, challenge).replace(
            "scope=mcp", "scope=mcp+endpoint%3A1"
        )
        + extra
    )
    response = client.get(f"/oauth/authorize/?{query}")
    assert response.status_code == 302
    assert response["Location"].startswith(REDIRECT_URI)
    query = parse_qs(urlparse(response["Location"]).query)
    assert query["error"] == ["invalid_scope"]
    assert query["iss"] == [settings.OAUTH2_PROVIDER["OIDC_ISS_ENDPOINT"]]


@pytest.mark.django_db
def test_refresh_cannot_widen_to_another_endpoint(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other = data_fixture.create_mcp_endpoint()
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint = MCPEndpoint.objects.get(id=tokens["endpoint_id"])

    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
            "scope": f"mcp endpoint:{endpoint.id} endpoint:{other.id}",
        },
    )
    assert response.status_code == 400, response.content
    assert response.json()["error"] == "invalid_scope"

    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
            "scope": f"mcp endpoint:{other.id}",
        },
    )
    assert response.status_code == 400, response.content
    assert response.json()["error"] == "invalid_scope"

    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
        },
    )
    assert response.status_code == 200, response.content
    assert response.json()["scope"] == f"mcp endpoint:{endpoint.id}"
