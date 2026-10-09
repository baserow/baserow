from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from oauth2_provider.exceptions import OAuthToolkitError
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error

from baserow.core.action.signals import action_done
from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    authorize_query,
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
    pkce_pair,
)


def _consent(client, api_client, token, workspace, client_id, tools):
    _, challenge = pkce_pair()
    return api_client.post(
        reverse("api:mcp:oauth_consent"),
        {
            "query": authorize_query(client_id, challenge),
            "allow": True,
            "workspace_id": workspace.id,
            "tools": tools,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.fixture
def done_actions():
    """
    The (type, params) of every action sent on `action_done`. These actions are
    not undoable, so they have no Action row and only reach the signal.
    """

    done = []

    def receiver(sender, action_type, action_params, **kwargs):
        done.append((action_type.type, action_params))

    action_done.connect(receiver, weak=False)
    yield done
    action_done.disconnect(receiver)


@pytest.mark.django_db
def test_consent_records_connect_action(client, api_client, data_fixture, done_actions):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client, client_name="My app")
    tools = enabled_tool_names()[:2]

    response = _consent(client, api_client, token, workspace, client_id, tools)

    assert response.status_code == 200
    endpoint = MCPEndpoint.objects.get(oauth_client_id=client_id)
    assert done_actions == [
        (
            "connect_mcp_oauth_client",
            {
                "endpoint_id": endpoint.id,
                "client_id": client_id,
                "client_name": "My app",
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
                "allowed_tools": tools,
                "tool_count": 2,
                "reconnect": False,
            },
        )
    ]


@pytest.mark.django_db
def test_second_consent_records_reconnect_with_new_tools(
    client, api_client, data_fixture, done_actions
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    names = enabled_tool_names()

    _consent(client, api_client, token, workspace, client_id, names[:2])
    _consent(client, api_client, token, workspace, client_id, names[:1])

    first, second = [params for _, params in done_actions]
    assert first["reconnect"] is False
    assert second["reconnect"] is True
    assert second["allowed_tools"] == names[:1]
    assert second["tool_count"] == 1


@pytest.mark.django_db
def test_disconnect_records_action(client, api_client, data_fixture, done_actions):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client, client_name="My app")
    tokens = obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    done_actions.clear()

    response = api_client.delete(
        reverse(
            "api:mcp:oauth_connection", kwargs={"connection_id": tokens["endpoint_id"]}
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 204
    assert done_actions == [
        (
            "disconnect_mcp_oauth_client",
            {
                "endpoint_id": tokens["endpoint_id"],
                "client_id": client_id,
                "client_name": "My app",
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
            },
        )
    ]


@pytest.mark.django_db
def test_consent_sends_posthog_event_after_commit(
    client, api_client, data_fixture, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    tools = enabled_tool_names()[:1]

    with patch("baserow.core.posthog.capture_user_event") as capture:
        with django_capture_on_commit_callbacks(execute=True):
            response = _consent(client, api_client, token, workspace, client_id, tools)
            capture.assert_not_called()

    assert response.status_code == 200
    endpoint = MCPEndpoint.objects.get(oauth_client_id=client_id)
    capture.assert_called_once_with(
        user,
        "connect_mcp_oauth_client",
        {"endpoint_id": endpoint.id, "workspace_id": workspace.id},
        workspace=workspace,
        session=None,
    )


@pytest.mark.django_db
def test_rolled_back_consent_sends_no_posthog_event(
    client, api_client, data_fixture, django_capture_on_commit_callbacks
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    error = OAuthToolkitError(
        error=CustomOAuth2Error(error="server_error"), redirect_uri=None
    )

    with (
        patch("baserow.api.mcp.oauth_views.issue_code", side_effect=error),
        patch("baserow.core.posthog.capture_user_event") as capture,
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = _consent(
            client, api_client, token, workspace, client_id, enabled_tool_names()
        )

    assert response.status_code == 400
    assert not MCPEndpoint.objects.filter(oauth_client_id=client_id).exists()
    capture.assert_not_called()
