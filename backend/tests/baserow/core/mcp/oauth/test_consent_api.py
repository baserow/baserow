from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings as django_settings
from django.shortcuts import reverse

import pytest
from oauth2_provider.exceptions import FatalClientError
from oauthlib.oauth2.rfc6749.errors import MismatchingRedirectURIError

from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import mcp_tool_registry
from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
    pkce_pair,
)

URL = "api:mcp:oauth_consent"


def _query(client, redirect_uri=REDIRECT_URI, **kwargs):
    _, challenge = pkce_pair()
    client_id = cimd_client(client, redirect_uri=redirect_uri, **kwargs)
    return authorize_query(client_id, challenge, redirect_uri=redirect_uri)


def _post(api_client, token, query, workspace, tools=None, allow=True):
    return api_client.post(
        reverse(URL),
        {
            "query": query,
            "allow": allow,
            "workspace_id": workspace.id,
            "tools": enabled_tool_names() if tools is None else tools,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_consent_is_404_when_oauth_is_disabled(
    client, api_client, data_fixture, settings
):
    # Resolving first loads the root urlconf with the OAuth routes mounted, so
    # later tests in this process still have them.
    url = reverse(URL)
    settings.BASEROW_MCP_OAUTH_ENABLED = False
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    query = _query(client)

    get = api_client.get(url, {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}")
    post = _post(api_client, token, query, workspace)

    assert get.status_code == 404
    assert post.status_code == 404
    assert not MCPEndpoint.objects.filter(oauth_client_id__isnull=False).exists()


@pytest.mark.django_db
def test_invalid_body_uses_the_baserow_error_envelope(client, api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    response = api_client.post(
        reverse(URL),
        {"allow": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_issued_code_redirect_carries_iss(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = _post(api_client, token, _query(client), workspace)

    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["redirect_url"]).query)
    assert "code" in query
    assert query["state"] == ["s1"]
    assert query["iss"] == [django_settings.OAUTH2_PROVIDER["OIDC_ISS_ENDPOINT"]]


@pytest.mark.django_db
def test_failed_code_issue_leaves_no_grant(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    error = FatalClientError(
        error=MismatchingRedirectURIError(), redirect_uri="https://evil.example/cb"
    )
    with patch("baserow.api.mcp.oauth_views.issue_code", side_effect=error):
        response = _post(api_client, token, _query(client), workspace)

    assert response.status_code == 400
    assert "redirect_url" not in response.json()
    assert not MCPEndpoint.objects.filter(oauth_client_id__isnull=False).exists()


@pytest.mark.django_db
def test_error_redirect_from_the_library_leaves_no_grant(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    location = f"{REDIRECT_URI}?error=invalid_request&state=s1"
    with patch(
        "oauth2_provider.oauth2_backends.OAuthLibCore.create_authorization_response",
        return_value=(location, {"Location": location}, None, 302),
    ):
        response = _post(api_client, token, _query(client), workspace)

    assert response.status_code == 200
    redirect_url = response.json()["redirect_url"]
    assert redirect_url.startswith(REDIRECT_URI)
    query = parse_qs(urlparse(redirect_url).query)
    assert query["error"] == ["invalid_request"]
    assert query["state"] == ["s1"]
    assert "code" not in query
    assert not MCPEndpoint.objects.filter(oauth_client_id__isnull=False).exists()


@pytest.mark.django_db
def test_consent_lists_only_workspaces_the_user_can_connect(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    allowed = data_fixture.create_workspace(user=user)
    denied = data_fixture.create_workspace(user=user)

    def can_create(actor, operation, workspace=None, context=None, **kwargs):
        return workspace.id == allowed.id

    with patch(
        "baserow.api.mcp.oauth_views.CoreHandler.check_permissions",
        side_effect=can_create,
    ):
        response = api_client.get(
            reverse(URL),
            {"query": _query(client)},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == 200
    assert [w["id"] for w in response.json()["workspaces"]] == [allowed.id]
    assert denied.id not in [w["id"] for w in response.json()["workspaces"]]


@pytest.mark.django_db
def test_consent_returns_the_existing_grant_tools(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    obtain_tokens(
        client,
        api_client,
        token,
        workspace,
        tools=["list_tables"],
        client_id=client_id,
    )
    _, challenge = pkce_pair()

    response = api_client.get(
        reverse(URL),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json()["grants"] == {str(workspace.id): ["list_tables"]}


@pytest.mark.django_db
def test_consent_lists_legacy_tools_for_a_null_grant(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    MCPEndpoint.objects.filter(oauth_client_id=client_id).update(allowed_tools=None)
    _, challenge = pkce_pair()

    response = api_client.get(
        reverse(URL),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json()["grants"] == {str(workspace.id): list(LEGACY_DEFAULT_TOOLS)}


@pytest.mark.django_db
def test_consent_flags_loopback_only_clients(client, api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    loopback = api_client.get(
        reverse(URL),
        {"query": _query(client)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    hosted = api_client.get(
        reverse(URL),
        {"query": _query(client, redirect_uri="https://claude.ai/api/callback")},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert loopback.json()["loopback_only"] is True
    assert hosted.json()["loopback_only"] is False


def _legacy_query(client, key):
    """The authorize query of a client given the old `/mcp/<key>/sse` URL."""

    resource = f"{django_settings.MCP_RESOURCE_URL}/{key}/sse"
    return _query(client) + "&" + urlencode({"resource": resource})


@pytest.mark.django_db
def test_consent_for_the_old_url_offers_only_its_workspace_and_tools(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_databases", "list_tables"]
    )

    response = api_client.get(
        reverse(URL),
        {"query": _legacy_query(client, legacy.key)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["legacy_endpoint"] == {
        "name": legacy.name,
        "workspace_id": workspace.id,
    }
    assert [w["id"] for w in data["workspaces"]] == [workspace.id]
    assert [t["name"] for t in data["tools"]] == ["list_databases", "list_tables"]


@pytest.mark.django_db
def test_consent_for_the_old_url_of_a_null_endpoint_offers_the_legacy_tools(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    legacy = data_fixture.create_mcp_endpoint(user=user, allowed_tools=None)

    response = api_client.get(
        reverse(URL),
        {"query": _legacy_query(client, legacy.key)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    assert {t["name"] for t in response.json()["tools"]} == set(
        LEGACY_DEFAULT_TOOLS
    ) & set(enabled_tool_names())


@pytest.mark.django_db
def test_consent_for_the_url_of_another_users_endpoint_is_rejected(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    other = data_fixture.create_mcp_endpoint()

    for key in [other.key, "does-not-exist"]:
        query = _legacy_query(client, key)
        get = api_client.get(
            reverse(URL), {"query": query}, HTTP_AUTHORIZATION=f"JWT {token}"
        )
        post = api_client.post(
            reverse(URL),
            {
                "query": query,
                "allow": True,
                "workspace_id": other.workspace_id,
                "tools": ["list_databases"],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        for response in [get, post]:
            assert response.status_code == 400
            assert response.json()["error"] == "legacy_endpoint_not_found"
    assert not MCPEndpoint.objects.filter(oauth_client_id__isnull=False).exists()


@pytest.mark.django_db
def test_consent_for_the_old_url_grants_its_workspace_and_tools(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_databases"]
    )

    # The form's choice is ignored: the client connects with the old key.
    response = _post(
        api_client,
        token,
        _legacy_query(client, legacy.key),
        other_workspace,
        tools=enabled_tool_names(),
    )

    assert response.status_code == 200
    assert "code=" in response.json()["redirect_url"]
    grant = MCPEndpoint.objects.get(oauth_client_id__isnull=False)
    assert grant.workspace_id == workspace.id
    assert grant.allowed_tools == ["list_databases"]


@pytest.mark.django_db
def test_consent_for_the_old_url_keeps_the_tools_of_an_existing_grant(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_databases"]
    )
    query = _legacy_query(client, legacy.key)
    client_id = parse_qs(query)["client_id"][0]
    grant = data_fixture.create_mcp_endpoint(
        user=user,
        workspace=workspace,
        oauth_client_id=client_id,
        allowed_tools=["list_databases", "create_rows"],
    )

    response = _post(api_client, token, query, workspace)

    assert response.status_code == 200
    grant.refresh_from_db()
    assert grant.allowed_tools == ["list_databases", "create_rows"]


@pytest.mark.django_db
def test_consent_for_the_old_url_of_a_trashed_workspace_is_rejected(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    workspace.trashed = True
    workspace.save()

    response = api_client.get(
        reverse(URL),
        {"query": _legacy_query(client, legacy.key)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "legacy_endpoint_not_found"


@pytest.mark.django_db
def test_consent_for_the_old_url_drops_disabled_tools_of_an_existing_grant(
    client, api_client, data_fixture, monkeypatch
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_databases"]
    )
    query = _legacy_query(client, legacy.key)
    client_id = parse_qs(query)["client_id"][0]
    grant = data_fixture.create_mcp_endpoint(
        user=user,
        workspace=workspace,
        oauth_client_id=client_id,
        allowed_tools=["list_databases", "create_rows"],
    )
    monkeypatch.setattr(mcp_tool_registry.get("create_rows"), "enabled", False)

    response = _post(api_client, token, query, workspace)

    assert response.status_code == 200, response.content
    grant.refresh_from_db()
    assert grant.allowed_tools == ["list_databases"]


@pytest.mark.django_db
def test_consent_for_the_old_url_without_enabled_tools_is_rejected(
    client, api_client, data_fixture, monkeypatch
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    legacy = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["create_rows"]
    )
    monkeypatch.setattr(mcp_tool_registry.get("create_rows"), "enabled", False)

    # A client posting the form itself still can't get a grant without tools.
    response = _post(
        api_client,
        token,
        _legacy_query(client, legacy.key),
        workspace,
        tools=["list_databases"],
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_TOOLS_NOT_AVAILABLE"
    assert not MCPEndpoint.objects.filter(oauth_client_id__isnull=False).exists()
