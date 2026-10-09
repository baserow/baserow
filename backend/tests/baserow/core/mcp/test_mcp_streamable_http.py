from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

import pytest
from asgiref.sync import async_to_sync
from httpx import ASGITransport, AsyncClient

from baserow.core.mcp import BaserowMCPServer, current_endpoint, current_key
from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import enabled_tool_names, obtain_tokens

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def _call(name, arguments=None):
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


HEADERS = {"Accept": "application/json, text/event-stream"}


def _post(body, auth=None, path="/mcp"):
    async def inner():
        app = BaserowMCPServer().sse_app()
        headers = dict(HEADERS)
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(path, json=body, headers=headers)
        # The handler must not leak the endpoint key into the caller's context.
        assert current_key.get(None) is None
        assert current_endpoint.get(None) is None
        return response

    return async_to_sync(inner)()


def _create_application():
    from oauth2_provider.models import Application

    return Application.objects.create(
        name="x",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="http://127.0.0.1/cb",
    )


def _create_grant(data_fixture, user, workspace=None):
    return data_fixture.create_mcp_endpoint(
        user=user,
        workspace=workspace or data_fixture.create_workspace(user=user),
        oauth_client_id=_create_application().client_id,
    )


def _create_raw_token(user, raw, scope, resource, expires=None, client_id=None):
    from oauth2_provider.models import AccessToken, Application

    if client_id:
        app = Application.objects.get(client_id=client_id)
    else:
        app = _create_application()
    return AccessToken.objects.create(
        user=user,
        application=app,
        token=raw,
        scope=scope,
        expires=expires or timezone.now() + timedelta(hours=1),
        resource=resource,
    )


@pytest.mark.django_db(transaction=True)
def test_no_token_gets_401_with_resource_metadata():
    response = _post(INIT)
    assert response.status_code == 401
    # RFC 6750 section 3.1: no error code when no credentials were sent.
    assert response.json() == {"detail": "Authentication required."}
    assert "error=" not in response.headers["www-authenticate"]
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert (
        "/.well-known/oauth-protected-resource/mcp"
        in response.headers["www-authenticate"]
    )


@pytest.mark.django_db(transaction=True)
def test_unknown_token_gets_401():
    response = _post(LIST, "does-not-exist")
    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_endpoint_key_lists_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    assert _post(INIT, endpoint.key).status_code == 200
    response = _post(LIST, endpoint.key)
    assert response.status_code == 200
    names = [t["name"] for t in response.json()["result"]["tools"]]
    assert "list_tables" in names


@pytest.mark.django_db(transaction=True)
def test_membership_is_checked_once_per_request(data_fixture):
    from unittest.mock import patch

    from baserow.core.subjects import UserSubjectType

    endpoint = data_fixture.create_mcp_endpoint()
    with patch.object(
        UserSubjectType, "is_in_workspace", autospec=True, return_value=True
    ) as check:
        response = _post(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, auth=endpoint.key
        )
    assert response.status_code == 200
    assert check.call_count == 1


@pytest.mark.django_db
def test_trailing_slash_is_not_served(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    response = _post(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        auth=endpoint.key,
        path="/mcp/",
    )
    assert response.status_code == 404


def test_www_authenticate_uses_the_slash_free_server_url(settings):
    from baserow.core.mcp.auth import www_authenticate

    settings.PUBLIC_BACKEND_URL = "https://br.example/"
    settings.MCP_AUTHORIZATION_SERVER_URL = "https://br.example"
    assert (
        'resource_metadata="https://br.example/.well-known/'
        'oauth-protected-resource/mcp"'
    ) in www_authenticate()


@pytest.mark.django_db(transaction=True)
def test_oauth_token_lists_tools(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    response = _post(LIST, tokens["access_token"])
    assert response.status_code == 200
    names = [t["name"] for t in response.json()["result"]["tools"]]
    assert names == enabled_tool_names()


@pytest.mark.django_db(transaction=True)
def test_oauth_token_only_lists_and_calls_granted_tools(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace, ["list_databases"])
    response = _post(LIST, tokens["access_token"])
    assert [t["name"] for t in response.json()["result"]["tools"]] == ["list_databases"]
    result = _post(_call("list_databases"), tokens["access_token"]).json()["result"]
    assert result["isError"] is False
    result = _post(_call("list_tables"), tokens["access_token"]).json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Tool 'list_tables' not found."


@pytest.mark.django_db(transaction=True)
def test_endpoint_key_honours_allowed_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=["list_tables"]
    )
    response = _post(LIST, endpoint.key)
    assert [t["name"] for t in response.json()["result"]["tools"]] == ["list_tables"]
    result = _post(_call("list_databases"), endpoint.key).json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Tool 'list_databases' not found."


@pytest.mark.django_db(transaction=True)
def test_endpoint_without_allowed_tools_gets_all_enabled_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    assert endpoint.allowed_tools is None
    response = _post(LIST, endpoint.key)
    names = [t["name"] for t in response.json()["result"]["tools"]]
    assert names == enabled_tool_names()


@pytest.mark.django_db(transaction=True)
def test_disabled_tool_cannot_be_called_by_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    response = _post(
        _call("create_table", {"database_id": database.id, "name": "Nope"}),
        endpoint.key,
    )
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Tool 'create_table' not found."
    assert not database.table_set.exists()


@pytest.mark.django_db(transaction=True)
def test_token_bound_to_endpoint_after_refresh(client, api_client, data_fixture):
    from baserow.core.mcp.auth import resolve_bearer

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    tokens = obtain_tokens(
        client, api_client, token, workspace, scope="mcp offline_access"
    )
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert response.status_code == 200
    endpoint, error = async_to_sync(resolve_bearer)(response.json()["access_token"])
    assert error is None and endpoint.id == tokens["endpoint_id"]


@pytest.mark.django_db(transaction=True)
def test_refresh_with_narrower_scope_stays_bound_to_the_grant(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint_id = tokens["endpoint_id"]

    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
            "scope": "mcp",
        },
    )
    assert response.status_code == 200, response.content
    refreshed = response.json()
    assert set(refreshed["scope"].split()) == {"mcp", f"endpoint:{endpoint_id}"}
    assert _post(LIST, refreshed["access_token"]).status_code == 200

    response = api_client.delete(
        reverse("api:mcp:oauth_connection", kwargs={"connection_id": endpoint_id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert _post(LIST, refreshed["access_token"]).status_code == 401
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refreshed["refresh_token"],
            "client_id": tokens["client_id"],
        },
    )
    assert response.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_token_after_user_left_workspace_gets_401(client, api_client, data_fixture):
    owner = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=owner, members=[user])
    tokens = obtain_tokens(client, api_client, token, workspace)
    workspace.workspaceuser_set.filter(user=user).delete()
    response = _post(LIST, tokens["access_token"])
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_without_endpoint_scope_gets_403(data_fixture):
    user = data_fixture.create_user()
    _create_raw_token(user, "plain-mcp-token", "mcp", [settings.MCP_RESOURCE_URL])
    response = _post(LIST, "plain-mcp-token")
    assert response.status_code == 403
    assert "insufficient_scope" in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_without_resource_gets_401(data_fixture):
    user = data_fixture.create_user()
    grant = _create_grant(data_fixture, user)
    _create_raw_token(
        user,
        "no-audience-token",
        f"mcp endpoint:{grant.id}",
        [],
        client_id=grant.oauth_client_id,
    )
    response = _post(LIST, "no-audience-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_for_other_resource_gets_401(data_fixture):
    user = data_fixture.create_user()
    grant = _create_grant(data_fixture, user)
    _create_raw_token(
        user,
        "foreign-token",
        f"mcp endpoint:{grant.id}",
        ["https://elsewhere.example.com/mcp"],
        client_id=grant.oauth_client_id,
    )
    assert _post(LIST, "foreign-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_expired_token_gets_401(data_fixture):
    user = data_fixture.create_user()
    grant = _create_grant(data_fixture, user)
    _create_raw_token(
        user,
        "expired-token",
        f"mcp endpoint:{grant.id}",
        [settings.MCP_RESOURCE_URL],
        expires=timezone.now() - timedelta(minutes=1),
        client_id=grant.oauth_client_id,
    )
    assert _post(LIST, "expired-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_token_for_other_users_endpoint_gets_401(data_fixture):
    owner = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner, members=[other])
    grant = _create_grant(data_fixture, owner, workspace)
    _create_raw_token(
        other,
        "other-user-token",
        f"mcp endpoint:{grant.id}",
        [settings.MCP_RESOURCE_URL],
        client_id=grant.oauth_client_id,
    )
    assert _post(LIST, "other-user-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_token_for_another_clients_grant_gets_401(data_fixture):
    user = data_fixture.create_user()
    own = _create_grant(data_fixture, user)
    other = _create_grant(data_fixture, user)
    _create_raw_token(
        user,
        "own-client-token",
        f"mcp endpoint:{own.id}",
        [settings.MCP_RESOURCE_URL],
        client_id=own.oauth_client_id,
    )
    _create_raw_token(
        user,
        "other-client-token",
        f"mcp endpoint:{other.id}",
        [settings.MCP_RESOURCE_URL],
        client_id=own.oauth_client_id,
    )
    assert _post(LIST, "own-client-token").status_code == 200
    response = _post(LIST, "other-client-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_without_an_application_gets_401(data_fixture):
    from oauth2_provider.models import AccessToken

    user = data_fixture.create_user()
    grant = _create_grant(data_fixture, user)
    AccessToken.objects.create(
        user=user,
        token="no-application-token",
        scope=f"mcp endpoint:{grant.id}",
        expires=timezone.now() + timedelta(hours=1),
        resource=[settings.MCP_RESOURCE_URL],
    )
    response = _post(LIST, "no-application-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_oauth_token_rejected_when_oauth_disabled(data_fixture, settings):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    grant = _create_grant(data_fixture, user, workspace)
    _create_raw_token(
        user,
        "flag-off-token",
        f"mcp endpoint:{grant.id}",
        [settings.MCP_RESOURCE_URL],
        client_id=grant.oauth_client_id,
    )
    assert _post(LIST, "flag-off-token").status_code == 200

    settings.BASEROW_MCP_OAUTH_ENABLED = False
    response = _post(LIST, "flag-off-token")
    assert response.status_code == 401
    # The metadata routes aren't mounted, so the challenge doesn't point at them.
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    assert _post(INIT).headers["www-authenticate"] == "Bearer"
    assert _post(LIST, endpoint.key).status_code == 200


def _get(path):
    async def inner():
        app = BaserowMCPServer().sse_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get(path)

    return async_to_sync(inner)()


@pytest.mark.django_db(transaction=True)
def test_oauth_grant_only_accepts_its_access_token(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint = MCPEndpoint.objects.get(id=tokens["endpoint_id"])
    assert endpoint.key is None
    response = _post(LIST, tokens["access_token"])
    assert response.status_code == 200
    assert response.json()["result"]["tools"]


@pytest.mark.django_db(transaction=True)
def test_oauth_grant_has_no_sse_key(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint = MCPEndpoint.objects.get(id=tokens["endpoint_id"])
    assert endpoint.key is None


@pytest.mark.django_db
def test_get_endpoint_resolves_grants_by_id_only(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    grant = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, oauth_client_id="https://claude.ai/x.json"
    )
    manual = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)

    async def lookup(var, value):
        ctx = var.set(value)
        try:
            return await BaserowMCPServer().get_endpoint()
        finally:
            var.reset(ctx)

    get = async_to_sync(lookup)
    assert grant.key is None
    assert get(current_key, manual.key).id == manual.id
    assert get(current_endpoint, grant).id == grant.id


@pytest.mark.django_db(transaction=True)
def test_initialize_is_captured_as_connected(data_fixture):
    from unittest.mock import patch

    endpoint = data_fixture.create_mcp_endpoint()
    with patch("baserow.core.posthog.capture_user_event") as mock_capture:
        init = _post(INIT, auth=endpoint.key)
        _post(LIST, auth=endpoint.key)

    assert init.status_code == 200
    mock_capture.assert_called_once_with(
        endpoint.user,
        "mcp_connected",
        {"endpoint_id": endpoint.id},
        workspace=endpoint.workspace,
    )
