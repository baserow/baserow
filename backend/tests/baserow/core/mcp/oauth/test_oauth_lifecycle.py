from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

import pytest
from asgiref.sync import async_to_sync
from oauth2_provider.models import AccessToken, Application, RefreshToken

from baserow.core.mcp.auth import resolve_bearer
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.tokens import revoke_endpoint_tokens
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens


@pytest.mark.django_db
def test_deleting_endpoint_removes_its_tokens(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    keep_workspace = data_fixture.create_workspace(user=user)
    endpoint_id = obtain_tokens(client, api_client, token, workspace)["endpoint_id"]
    kept = obtain_tokens(client, api_client, token, keep_workspace)
    endpoint = MCPEndpoint.objects.get(id=endpoint_id)
    keep = MCPEndpoint.objects.get(id=kept["endpoint_id"])
    MCPEndpointHandler().delete_endpoint(user, endpoint)
    assert not AccessToken.objects.filter(
        scope__contains=f"endpoint:{endpoint_id}"
    ).exists()
    # Only the kept endpoint's refresh token is left for this user.
    remaining = RefreshToken.objects.filter(user=user, revoked__isnull=True)
    assert remaining.count() == 1
    assert set(remaining.get().access_token.scope.split()) == {
        "mcp",
        f"endpoint:{keep.id}",
    }
    endpoint_kept, error = async_to_sync(resolve_bearer)(kept["access_token"])
    assert error is None and endpoint_kept.id == keep.id


@pytest.mark.django_db
def test_revoke_endpoint_tokens_matches_scope_exactly(data_fixture):
    user = data_fixture.create_user()
    application = Application.objects.create(
        name="app",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )
    expires = timezone.now() + timedelta(hours=1)

    def make(value, scope):
        access = AccessToken.objects.create(
            user=user,
            application=application,
            token=value,
            expires=expires,
            scope=scope,
        )
        RefreshToken.objects.create(
            user=user,
            application=application,
            token=f"r-{value}",
            access_token=access,
        )
        return access

    one = make("a1", "mcp endpoint:1")
    twelve = make("a12", "mcp endpoint:12")
    revoke_endpoint_tokens(1)
    assert not AccessToken.objects.filter(id=one.id).exists()
    assert not RefreshToken.objects.filter(token="r-a1").exists()
    assert AccessToken.objects.filter(id=twelve.id).exists()
    assert RefreshToken.objects.filter(token="r-a12").exists()


@pytest.mark.django_db
def test_flag_off_refuses_oauth_token_but_accepts_key(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace)
    with override_settings(BASEROW_MCP_OAUTH_ENABLED=False):
        _, error = async_to_sync(resolve_bearer)(tokens["access_token"])
        assert error == "invalid_token"
        found, error = async_to_sync(resolve_bearer)(endpoint.key)
        assert error is None and found.id == endpoint.id
