from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from oauth2_provider.exceptions import FatalClientError
from oauth2_provider.models import get_application_model
from oauthlib.oauth2.rfc6749.errors import MismatchingRedirectURIError

from baserow.core.mcp.actions import (
    ConnectMCPOAuthClientActionType,
    DisconnectMCPOAuthClientActionType,
)
from baserow_enterprise.audit_log.models import AuditLogEntry
from tests.baserow.core.mcp.oauth.helpers import enabled_tool_names


@pytest.mark.django_db
def test_connecting_and_disconnecting_an_mcp_client_are_audit_logged(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    endpoint = ConnectMCPOAuthClientActionType.do(
        user, workspace, "https://claude.ai/oauth/x.json", "My app", ["list_tables"]
    )
    DisconnectMCPOAuthClientActionType.do(user, endpoint)

    entries = AuditLogEntry.objects.order_by("id")
    assert [e.action_type for e in entries] == [
        "connect_mcp_oauth_client",
        "disconnect_mcp_oauth_client",
    ]
    assert entries[0].workspace_id == workspace.id
    assert entries[0].user_id == user.id


@pytest.mark.django_db
def test_rolled_back_consent_leaves_no_audit_log_entry(
    api_client, enterprise_data_fixture, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    get_application_model().objects.create(
        client_id="https://claude.ai/oauth/x.json",
        name="My app",
        redirect_uris="http://127.0.0.1:33418/callback",
        client_type="public",
        authorization_grant_type="authorization-code",
    )
    credentials = {
        "client_id": "https://claude.ai/oauth/x.json",
        "redirect_uri": "http://127.0.0.1:33418/callback",
    }
    error = FatalClientError(
        error=MismatchingRedirectURIError(), redirect_uri="https://evil.example/cb"
    )

    with (
        patch(
            "baserow.api.mcp.oauth_views.validate_query",
            return_value=(None, credentials),
        ),
        patch("baserow.api.mcp.oauth_views.issue_code", side_effect=error),
    ):
        response = api_client.post(
            reverse("api:mcp:oauth_consent"),
            {
                "query": "x",
                "allow": True,
                "workspace_id": workspace.id,
                "tools": enabled_tool_names(),
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.json()["error"] == "invalid_request"
    assert response.status_code == 400
    assert not AuditLogEntry.objects.filter(
        action_type="connect_mcp_oauth_client"
    ).exists()
