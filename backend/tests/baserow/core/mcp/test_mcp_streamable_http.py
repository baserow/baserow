from datetime import timedelta

from django.conf import settings
from django.utils import timezone

import pytest
from asgiref.sync import async_to_sync
from httpx import ASGITransport, AsyncClient

from baserow.core.mcp import BaserowMCPServer, current_key
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
        return response

    return async_to_sync(inner)()


def _create_raw_token(user, raw, scope, resource, expires=None):
    from oauth2_provider.models import AccessToken, Application

    app = Application.objects.create(
        name="x",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="http://127.0.0.1/cb",
    )
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
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert (
        "/.well-known/oauth-protected-resource/mcp"
        in response.headers["www-authenticate"]
    )


@pytest.mark.django_db(transaction=True)
def test_unknown_token_gets_401():
    response = _post(LIST, "does-not-exist")
    assert response.status_code == 401
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
def test_trailing_slash_is_served(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    response = _post(LIST, endpoint.key, path="/mcp/")
    assert response.status_code == 200
    assert response.json()["result"]["tools"]


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
    tokens = obtain_tokens(client, api_client, token, workspace)
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
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    _create_raw_token(user, "no-audience-token", f"mcp endpoint:{endpoint.id}", [])
    response = _post(LIST, "no-audience-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_for_other_resource_gets_401(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    _create_raw_token(
        user,
        "foreign-token",
        f"mcp endpoint:{endpoint.id}",
        ["https://elsewhere.example.com/mcp"],
    )
    assert _post(LIST, "foreign-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_expired_token_gets_401(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    _create_raw_token(
        user,
        "expired-token",
        f"mcp endpoint:{endpoint.id}",
        [settings.MCP_RESOURCE_URL],
        expires=timezone.now() - timedelta(minutes=1),
    )
    assert _post(LIST, "expired-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_token_for_other_users_endpoint_gets_401(data_fixture):
    owner = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner, members=[other])
    endpoint = data_fixture.create_mcp_endpoint(user=owner, workspace=workspace)
    _create_raw_token(
        other,
        "other-user-token",
        f"mcp endpoint:{endpoint.id}",
        [settings.MCP_RESOURCE_URL],
    )
    assert _post(LIST, "other-user-token").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_oauth_token_rejected_when_oauth_disabled(data_fixture, settings):
    settings.BASEROW_MCP_OAUTH_ENABLED = False
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    _create_raw_token(
        user,
        "flag-off-token",
        f"mcp endpoint:{endpoint.id}",
        [settings.MCP_RESOURCE_URL],
    )
    assert _post(LIST, "flag-off-token").status_code == 401
    assert _post(LIST, endpoint.key).status_code == 200
