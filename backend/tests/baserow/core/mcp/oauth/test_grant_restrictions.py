from urllib.parse import parse_qs, urlparse

from django.conf import settings

import pytest
from oauth2_provider.models import AccessToken, Application

from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    obtain_tokens,
    pkce_pair,
    register_dcr_client,
)


def register(client, **metadata):
    return client.post(
        "/oauth/register/",
        {
            "client_name": "Client",
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            **metadata,
        },
        content_type="application/json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "metadata",
    [
        {"grant_types": ["password"]},
        {"grant_types": ["client_credentials"]},
        {"grant_types": ["implicit"]},
        {"grant_types": ["urn:ietf:params:oauth:grant-type:device_code"]},
        {"grant_types": ["authorization_code"], "response_types": ["token"]},
        {"grant_types": ["authorization_code"], "response_types": ["code", "token"]},
        {"grant_types": "authorization_code"},
        {"response_types": "code"},
    ],
)
def test_dcr_rejects_grants_other_than_authorization_code(client, metadata):
    count = Application.objects.count()
    response = register(client, **metadata)
    assert response.status_code == 400, response.content
    assert response.json()["error"] == "invalid_client_metadata"
    assert Application.objects.count() == count


@pytest.mark.django_db
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"grant_types": ["authorization_code"]},
        {"grant_types": ["authorization_code", "refresh_token"]},
        {"grant_types": ["authorization_code"], "response_types": ["code"]},
    ],
)
def test_dcr_accepts_authorization_code(client, metadata):
    response = register(client, **metadata)
    assert response.status_code == 201, response.content


@pytest.mark.django_db
def test_dcr_update_cannot_switch_to_password_grant(client):
    response = register(client)
    data = response.json()
    response = client.put(
        urlparse(data["registration_client_uri"]).path,
        {
            "client_name": "Client",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["password"],
            "token_endpoint_auth_method": "none",
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {data['registration_access_token']}",
    )
    assert response.status_code == 400, response.content
    application = Application.objects.get(client_id=data["client_id"])
    assert application.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE


@pytest.mark.django_db
def test_password_grant_is_refused(client, data_fixture):
    # An application allowed to use the password grant can only exist if created
    # outside DCR; the token endpoint must still refuse it.
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
    client_id = register_dcr_client(client)
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
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    other = data_fixture.create_mcp_endpoint()
    tokens = obtain_tokens(client, api_client, token, endpoint)

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
