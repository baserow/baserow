from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from asgiref.sync import async_to_sync
from oauth2_provider.models import AccessToken

from baserow.core.mcp.auth import resolve_bearer
from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
)

LIST_URL = "api:mcp:oauth_connections"


def _detail_url(connection_id):
    return reverse("api:mcp:oauth_connection", kwargs={"connection_id": connection_id})


@pytest.mark.django_db
def test_list_connections(client, api_client, data_fixture, settings):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, name="Sales")
    other_workspace = data_fixture.create_workspace(user=user, name="Ops")
    data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    client_id = cimd_client(client, client_name="Claude")
    full = obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    limited = obtain_tokens(
        client, api_client, token, other_workspace, tools=["list_tables"]
    )
    # Another user's grant is not listed.
    other_user, other_token = data_fixture.create_user_and_token()
    obtain_tokens(
        client,
        api_client,
        other_token,
        data_fixture.create_workspace(user=other_user),
    )

    response = api_client.get(reverse(LIST_URL), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200
    data = response.json()
    assert data["oauth_enabled"] is True
    assert data["mcp_url"] == settings.MCP_RESOURCE_URL
    assert [c["id"] for c in data["connections"]] == [
        full["endpoint_id"],
        limited["endpoint_id"],
    ]
    first, second = data["connections"]
    assert first["client_name"] == "Claude"
    assert first["verified"] is True
    assert first["verified_host"] == "claude.ai"
    assert first["workspace_id"] == workspace.id
    assert first["workspace_name"] == "Sales"
    assert first["allowed_tools"] == enabled_tool_names()
    assert first["tool_count"] == len(enabled_tool_names())
    assert first["created"]
    assert second["workspace_name"] == "Ops"
    assert second["allowed_tools"] == ["list_tables"]
    assert second["tool_count"] == 1


@pytest.mark.django_db
def test_list_connections_counts_all_tools_when_unrestricted(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_mcp_endpoint(
        user=user,
        workspace=workspace,
        name="Gone client",
        oauth_client_id="https://claude.ai/removed.json",
    )
    response = api_client.get(reverse(LIST_URL), HTTP_AUTHORIZATION=f"JWT {token}")
    (connection,) = response.json()["connections"]
    assert connection["client_name"] == "Gone client"
    assert connection["verified"] is False
    assert connection["verified_host"] is None
    assert connection["allowed_tools"] is None
    assert connection["tool_count"] == len(enabled_tool_names())


@pytest.mark.django_db
def test_list_connections_hides_grants_in_workspaces_the_user_left(
    client, api_client, data_fixture
):
    owner = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    left = data_fixture.create_workspace(user=owner, members=[user])
    kept = data_fixture.create_workspace(user=user)
    obtain_tokens(client, api_client, token, left)
    kept_id = obtain_tokens(client, api_client, token, kept)["endpoint_id"]
    left.workspaceuser_set.filter(user=user).delete()

    response = api_client.get(reverse(LIST_URL), HTTP_AUTHORIZATION=f"JWT {token}")
    assert [c["id"] for c in response.json()["connections"]] == [kept_id]


@pytest.mark.django_db
def test_list_connections_when_oauth_disabled(api_client, data_fixture, settings):
    url = reverse(LIST_URL)
    settings.BASEROW_MCP_OAUTH_ENABLED = False
    user, token = data_fixture.create_user_and_token()
    data_fixture.create_mcp_endpoint(user=user, oauth_client_id="https://x/y.json")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200
    assert response.json() == {
        "oauth_enabled": False,
        "mcp_url": None,
        "connections": [],
    }


@pytest.mark.django_db
def test_list_connections_requires_auth(api_client):
    assert api_client.get(reverse(LIST_URL)).status_code == 401


@pytest.mark.django_db
def test_disconnect_deletes_grant_and_revokes_tokens(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint_id = tokens["endpoint_id"]

    response = api_client.delete(
        _detail_url(endpoint_id), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 204
    assert not MCPEndpoint.objects.filter(id=endpoint_id).exists()
    assert not AccessToken.objects.filter(
        scope__contains=f"endpoint:{endpoint_id}"
    ).exists()
    endpoint, error = async_to_sync(resolve_bearer)(tokens["access_token"])
    assert endpoint is None and error == "invalid_token"


@pytest.mark.django_db
def test_disconnect_other_users_grant_is_404(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=other_user, members=[user])
    endpoint_id = obtain_tokens(client, api_client, other_token, workspace)[
        "endpoint_id"
    ]
    response = api_client.delete(
        _detail_url(endpoint_id), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"
    assert MCPEndpoint.objects.filter(id=endpoint_id).exists()


@pytest.mark.django_db
def test_disconnect_works_without_mcp_endpoint_permissions(
    client, api_client, data_fixture
):
    from baserow.core.exceptions import PermissionDenied
    from baserow.core.handler import CoreHandler
    from baserow.core.mcp.operations import (
        DeleteMCPEndpointOperationType,
        ReadMCPEndpointOperationType,
    )

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint_id = tokens["endpoint_id"]

    original = CoreHandler.check_permissions
    denied = {ReadMCPEndpointOperationType.type, DeleteMCPEndpointOperationType.type}

    def check_permissions(self, actor, operation_name, *args, **kwargs):
        if operation_name in denied:
            raise PermissionDenied()
        return original(self, actor, operation_name, *args, **kwargs)

    with patch.object(CoreHandler, "check_permissions", check_permissions):
        response = api_client.delete(
            _detail_url(endpoint_id), HTTP_AUTHORIZATION=f"JWT {token}"
        )

    assert response.status_code == 204
    assert not MCPEndpoint.objects.filter(id=endpoint_id).exists()
    endpoint, error = async_to_sync(resolve_bearer)(tokens["access_token"])
    assert endpoint is None and error == "invalid_token"


@pytest.mark.django_db
def test_disconnect_legacy_endpoint_is_404(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    endpoint = data_fixture.create_mcp_endpoint(user=user)
    response = api_client.delete(
        _detail_url(endpoint.id), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 404
    assert MCPEndpoint.objects.filter(id=endpoint.id).exists()


@pytest.mark.django_db
def test_tool_count_ignores_disabled_tools(client, api_client, data_fixture):
    from baserow.core.mcp.handler import MCPEndpointHandler

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    MCPEndpointHandler().grant_oauth_client(
        user,
        workspace,
        cimd_client(client),
        "c",
        ["list_tables", "no_longer_registered"],
    )

    response = api_client.get(reverse(LIST_URL), HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.json()["connections"][0]["tool_count"] == 1


@pytest.mark.django_db
def test_disconnect_oauth_grant_rejects_other_users_and_key_endpoints(data_fixture):
    from baserow.core.mcp.exceptions import MCPEndpointDoesNotBelongToUser
    from baserow.core.mcp.handler import MCPEndpointHandler

    user = data_fixture.create_user()
    grant = data_fixture.create_mcp_endpoint(oauth_client_id="https://x/y.json")
    key_endpoint = data_fixture.create_mcp_endpoint(user=user)

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        MCPEndpointHandler().disconnect_oauth_grant(user, grant)
    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        MCPEndpointHandler().disconnect_oauth_grant(user, key_endpoint)
    assert MCPEndpoint.objects.filter(id__in=[grant.id, key_endpoint.id]).count() == 2
