from unittest.mock import patch

from django.shortcuts import reverse

import pytest

from baserow.core.action.signals import action_done
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS
from baserow.core.mcp.groups import GROUP_DATABASE_READ, mcp_tool_group_registry
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.operations import UpdateMCPEndpointOperationType
from baserow.core.mcp.registries import MCPTool, mcp_tool_registry
from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
    pkce_pair,
)
from tests.baserow.core.mcp.test_mcp_streamable_http import LIST, _call, _post


def _url(connection_id):
    return reverse("api:mcp:oauth_connection", kwargs={"connection_id": connection_id})


def _patch(api_client, token, connection_id, tools):
    return api_client.patch(
        _url(connection_id),
        {"allowed_tools": tools},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.fixture
def done_actions():
    done = []

    def receiver(sender, action_type, action_params, **kwargs):
        done.append((action_type.type, action_params))

    action_done.connect(receiver, weak=False)
    yield done
    action_done.disconnect(receiver)


@pytest.fixture
def disabled_tool():
    """A read tool that is registered but disabled."""

    class Disabled(MCPTool):
        """Disabled."""

        type = "disabled_test_tool"
        group = GROUP_DATABASE_READ
        read_only = True
        enabled = False

    mcp_tool_registry.register(Disabled())
    yield "disabled_test_tool"
    mcp_tool_registry.unregister("disabled_test_tool")


@pytest.mark.django_db(transaction=True)
def test_change_tools_applies_to_the_existing_token(
    client, api_client, data_fixture, done_actions
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace, ["list_databases"])

    response = _patch(api_client, token, tokens["endpoint_id"], ["list_tables"])

    assert response.status_code == 200, response.content
    assert response.json()["allowed_tools"] == ["list_tables"]
    assert response.json()["tool_count"] == 1
    listed = _post(LIST, tokens["access_token"]).json()["result"]["tools"]
    assert [tool["name"] for tool in listed] == ["list_tables"]
    result = _post(_call("list_databases"), tokens["access_token"]).json()["result"]
    assert result["isError"] is True
    assert [action for action, _ in done_actions][-1] == "update_mcp_endpoint_tools"
    params = done_actions[-1][1]
    assert params["original_allowed_tools"] == ["list_databases"]
    assert params["allowed_tools"] == ["list_tables"]


@pytest.mark.django_db
def test_change_tools_stores_names_in_registry_order(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace)["endpoint_id"]

    response = _patch(api_client, token, endpoint_id, ["list_tables", "list_databases"])

    assert response.status_code == 200
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == [
        "list_databases",
        "list_tables",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tools",
    [["list_tables", "not_a_tool"], ["delete_table"], [], ["list_tables"] * 2],
)
def test_change_tools_rejects_invalid_lists(client, api_client, data_fixture, tools):
    # `delete_table` is registered but disabled.
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace)["endpoint_id"]

    response = _patch(api_client, token, endpoint_id, tools)

    assert response.status_code == 400
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == (
        enabled_tool_names()
    )


@pytest.mark.django_db
def test_change_tools_rejects_a_disabled_tool(
    client, api_client, data_fixture, disabled_tool
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace, ["list_tables"])[
        "endpoint_id"
    ]

    response = _patch(api_client, token, endpoint_id, [disabled_tool])

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_TOOLS_NOT_AVAILABLE"
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == ["list_tables"]


@pytest.mark.django_db
def test_change_tools_of_another_users_connection_is_404(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=other_user, members=[user])
    endpoint_id = obtain_tokens(
        client, api_client, other_token, workspace, ["list_tables"]
    )["endpoint_id"]

    response = _patch(api_client, token, endpoint_id, ["list_databases"])

    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == ["list_tables"]


@pytest.mark.django_db
def test_change_tools_of_an_endpoint_key_through_the_oauth_route_is_404(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, allowed_tools=["list_tables"]
    )

    response = _patch(api_client, token, endpoint.id, ["list_databases"])

    assert response.status_code == 404


@pytest.mark.django_db
def test_change_tools_needs_the_update_permission(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace, ["list_tables"])[
        "endpoint_id"
    ]
    original = CoreHandler.check_permissions

    def check_permissions(self, actor, operation_name, *args, **kwargs):
        if operation_name == UpdateMCPEndpointOperationType.type:
            raise PermissionDenied()
        return original(self, actor, operation_name, *args, **kwargs)

    with patch.object(CoreHandler, "check_permissions", check_permissions):
        response = _patch(api_client, token, endpoint_id, ["list_databases"])

    assert response.status_code == 401
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == ["list_tables"]


@pytest.mark.django_db
def test_list_connections_returns_the_tools_to_pick_from(
    client, api_client, data_fixture, disabled_tool
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    obtain_tokens(client, api_client, token, workspace, ["list_tables"])

    response = api_client.get(
        reverse("api:mcp:oauth_connections"), HTTP_AUTHORIZATION=f"JWT {token}"
    )

    data = response.json()
    assert [tool["name"] for tool in data["tools"]] == enabled_tool_names()
    assert data["tools"][0]["group"]
    listed = {tool["group"] for tool in data["tools"]}
    assert [group["type"] for group in data["groups"]] == [
        group.type
        for group in mcp_tool_group_registry.get_ordered()
        if group.type in listed
    ]
    assert disabled_tool not in [tool["name"] for tool in data["tools"]]
    (connection,) = data["connections"]
    assert connection["tool_count"] == 1


@pytest.mark.django_db
def test_endpoint_key_tools_can_be_changed(api_client, data_fixture, done_actions):
    user, token = data_fixture.create_user_and_token()
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, allowed_tools=["list_tables"]
    )
    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint.id})

    response = api_client.patch(
        url,
        {"allowed_tools": ["list_databases"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["allowed_tools"] == ["list_databases"]
    endpoint.refresh_from_db()
    assert endpoint.allowed_tools == ["list_databases"]
    assert endpoint.name == response.json()["name"]
    assert [action for action, _ in done_actions] == ["update_mcp_endpoint_tools"]

    response = api_client.patch(
        url,
        {"allowed_tools": ["nope"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_endpoint_key_lists_its_tools(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    endpoint = data_fixture.create_mcp_endpoint(user=user, allowed_tools=None)

    response = api_client.get(
        reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.json()["allowed_tools"] == LEGACY_DEFAULT_TOOLS


@pytest.mark.django_db
def test_change_tools_keeps_a_stored_disabled_tool(
    client, api_client, data_fixture, disabled_tool
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace, ["list_tables"])[
        "endpoint_id"
    ]
    MCPEndpoint.objects.filter(id=endpoint_id).update(
        allowed_tools=["list_tables", disabled_tool]
    )

    # Settings doesn't list disabled tools, so it never sends them.
    response = _patch(api_client, token, endpoint_id, ["list_tables", "list_databases"])

    assert response.status_code == 200, response.content
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == [
        "list_databases",
        "list_tables",
        disabled_tool,
    ]
    assert response.json()["tool_count"] == 2


@pytest.mark.django_db
def test_removing_tools_needs_no_permission(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(
        client, api_client, token, workspace, ["list_databases", "list_tables"]
    )["endpoint_id"]

    with patch.object(CoreHandler, "check_permissions", side_effect=PermissionDenied):
        response = _patch(api_client, token, endpoint_id, ["list_tables"])

    assert response.status_code == 200, response.content
    assert MCPEndpoint.objects.get(id=endpoint_id).allowed_tools == ["list_tables"]


@pytest.mark.django_db
def test_consent_rejects_a_disabled_tool(
    client, api_client, data_fixture, disabled_tool
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    _, challenge = pkce_pair()

    response = api_client.post(
        reverse("api:mcp:oauth_consent"),
        {
            "query": authorize_query(cimd_client(client), challenge),
            "allow": True,
            "workspace_id": workspace.id,
            "tools": ["list_tables", disabled_tool],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    # The serializer only accepts enabled tool names.
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_endpoint_key_patch_without_changes_is_rejected(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    endpoint = data_fixture.create_mcp_endpoint(user=user)

    response = api_client.patch(
        reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint.id}),
        {"allowed_tool": ["list_tables"]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
