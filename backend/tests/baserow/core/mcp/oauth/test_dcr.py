import json
from datetime import timedelta

from django.shortcuts import reverse
from django.test import Client, override_settings
from django.utils import timezone

import pytest
from freezegun import freeze_time
from oauth2_provider.models import get_access_token_model, get_application_model

from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.tasks import (
    clear_expired_mcp_oauth_tokens,
    delete_unused_mcp_oauth_clients,
)
from baserow.throttling.types import RateLimit
from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    cimd_client,
    obtain_tokens,
    pkce_pair,
)


def register(client, redirect_uris=(REDIRECT_URI,), ip="1.1.1.1", **extra):
    body = {
        "client_name": "Cursor",
        "redirect_uris": list(redirect_uris),
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        **extra,
    }
    # A None value means the client leaves the field out.
    body = {key: value for key, value in body.items() if value is not None}
    return client.post(
        "/oauth/register/",
        json.dumps(body),
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=ip,
    )


@pytest.mark.django_db
def test_registration_is_advertised(client):
    data = client.get("/.well-known/oauth-authorization-server").json()
    assert data["registration_endpoint"].endswith("/oauth/register/")
    assert data["client_id_metadata_document_supported"] is True
    assert "none" in data["token_endpoint_auth_methods_supported"]


@pytest.mark.django_db
def test_registered_client_completes_the_flow(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = register(client)
    assert response.status_code == 201, response.content
    client_id = response.json()["client_id"]
    # RFC 7592 management isn't offered.
    assert "registration_client_uri" not in response.json()
    assert "registration_access_token" not in response.json()

    tokens = obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    assert tokens["access_token"]


@pytest.mark.django_db
def test_dcr_client_is_not_verified(client, api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    client_id = register(client).json()["client_id"]
    _, challenge = pkce_pair()

    data = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    ).json()

    assert data["verified"] is False
    assert data["verified_host"] is None
    assert data["client_name"] == "Cursor"
    assert data["redirect_host"] == "127.0.0.1"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "uri",
    [
        "http://evil.example/cb",
        "javascript://x",
        "custom-app:/cb",
        "cursor://anysphere.cursor-retrieval/oauth/callback",
        # DOT splits stored redirect URIs on whitespace, so these would become two.
        "http://localhost/cb http://evil.example/cb",
        "http://localhost/cb\nhttp://evil.example/cb",
        "http://localhost/cb\xa0http://evil.example/cb",
    ],
)
def test_registration_rejects_unsafe_redirect_uris(client, uri):
    response = register(client, redirect_uris=[uri])
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra",
    [
        {"token_endpoint_auth_method": "client_secret_basic"},
        {"grant_types": ["client_credentials"]},
        {"grant_types": ["authorization_code", "password"]},
    ],
)
def test_registration_is_limited_to_public_code_clients(client, extra):
    response = register(client, **extra)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"


@pytest.mark.django_db
def test_registration_defaults_to_a_public_client(client):
    response = register(client, token_endpoint_auth_method=None)
    assert response.status_code == 201, response.content
    assert response.json()["token_endpoint_auth_method"] == "none"
    assert "client_secret" not in response.json()


@pytest.mark.django_db
def test_management_endpoint_is_not_offered(client):
    client_id = register(client).json()["client_id"]
    assert client.get(f"/oauth/register/{client_id}/").status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["put", "delete"])
def test_management_endpoint_is_not_offered_for_writes(method):
    client = Client(enforce_csrf_checks=True)
    client_id = register(client).json()["client_id"]
    response = getattr(client, method)(f"/oauth/register/{client_id}/")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "uri",
    ["https://app.example/cb", "http://localhost:1234/cb", "http://[::1]:5/cb"],
)
def test_registration_accepts_safe_redirect_uris(client, uri):
    assert register(client, redirect_uris=[uri]).status_code == 201


@pytest.mark.django_db
def test_registration_is_off_when_dcr_is_disabled(client, settings):
    settings.OAUTH2_PROVIDER = {**settings.OAUTH2_PROVIDER, "DCR_ENABLED": False}
    assert register(client).status_code == 404
    data = client.get("/.well-known/oauth-authorization-server").json()
    assert "registration_endpoint" not in data


@pytest.mark.django_db
@override_settings(
    BASEROW_MCP_OAUTH_REGISTRATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=60, number_of_calls=2),
    )
)
def test_registration_is_rate_limited_per_ip(client):
    with freeze_time("2026-01-01 12:00:00"):
        assert register(client).status_code == 201
        assert register(client).status_code == 201
        limited = register(client)
        other_ip = register(client, ip="2.2.2.2")
    assert limited.status_code == 429
    assert limited.json()["error"] == "slow_down"
    assert other_ip.status_code == 201


@pytest.mark.django_db
def test_unused_dcr_clients_are_deleted(client, api_client, data_fixture):
    Application = get_application_model()
    with freeze_time(timezone.now() - timedelta(days=2)):
        # The JWT is issued at the frozen time so it's valid there.
        user, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=user)
        unused = register(client).json()["client_id"]
        used = register(client, ip="2.2.2.2").json()["client_id"]
        obtain_tokens(client, api_client, token, workspace, client_id=used)
    recent = register(client, ip="3.3.3.3").json()["client_id"]

    delete_unused_mcp_oauth_clients()

    remaining = set(Application.objects.values_list("client_id", flat=True))
    assert unused not in remaining
    assert {used, recent} <= remaining


def load_cimd_client(api_client, token):
    """Loads a new CIMD client into the Application table and returns its id."""

    client_id = cimd_client(api_client)
    _, challenge = pkce_pair()
    api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert get_application_model().objects.filter(client_id=client_id).exists()
    return client_id


@pytest.mark.django_db
def test_unused_cimd_clients_are_deleted(client, api_client, data_fixture):
    Application = get_application_model()
    with freeze_time(timezone.now() - timedelta(days=2)):
        user, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=user)
        unused = load_cimd_client(api_client, token)
        used = obtain_tokens(client, api_client, token, workspace)["client_id"]
    recent = load_cimd_client(api_client, data_fixture.generate_token(user))

    delete_unused_mcp_oauth_clients()

    remaining = set(Application.objects.values_list("client_id", flat=True))
    assert unused not in remaining
    assert {used, recent} <= remaining


@pytest.mark.django_db
def test_dcr_client_with_a_grant_in_a_trashed_workspace_is_kept(
    client, api_client, data_fixture
):
    Application = get_application_model()
    with freeze_time(timezone.now() - timedelta(days=2)):
        user, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=user)
        client_id = register(client).json()["client_id"]
        obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    workspace.trashed = True
    workspace.save()

    delete_unused_mcp_oauth_clients()

    assert Application.objects.filter(client_id=client_id).exists()


@pytest.mark.django_db
def test_dcr_client_whose_grant_was_removed_is_deleted_with_its_tokens(
    client, api_client, data_fixture
):
    Application = get_application_model()
    with freeze_time(timezone.now() - timedelta(days=2)):
        user, token = data_fixture.create_user_and_token()
        workspace = data_fixture.create_workspace(user=user)
        client_id = register(client).json()["client_id"]
        obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    # Leaves the client's access and refresh tokens behind.
    MCPEndpoint.objects.filter(oauth_client_id=client_id).delete()

    delete_unused_mcp_oauth_clients()

    assert not Application.objects.filter(client_id=client_id).exists()


@pytest.mark.django_db
def test_registration_tokens_expire_and_are_cleared(client):
    client_id = register(client).json()["client_id"]
    tokens = get_access_token_model().objects.filter(application__client_id=client_id)
    assert tokens.get().expires <= timezone.now() + timedelta(hours=1)

    with freeze_time(timezone.now() + timedelta(hours=2)):
        clear_expired_mcp_oauth_tokens()

    assert not tokens.exists()


@pytest.mark.django_db
def test_client_without_a_name_is_named_by_its_redirect_host(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = register(client, client_name=None).json()["client_id"]
    _, challenge = pkce_pair()

    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    assert response.json()["client_name"] == "127.0.0.1"

    endpoint_id = obtain_tokens(
        client, api_client, token, workspace, client_id=client_id
    )["endpoint_id"]
    assert MCPEndpoint.objects.get(id=endpoint_id).name == "127.0.0.1"
    connections = api_client.get(
        reverse("api:mcp:oauth_connections"), HTTP_AUTHORIZATION=f"JWT {token}"
    ).json()["connections"]
    assert [c["client_name"] for c in connections] == ["127.0.0.1"]
