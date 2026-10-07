import pytest
from oauth2_provider.models import AccessToken, RefreshToken

from baserow.core.handler import CoreHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.tokens import revoke_endpoint_tokens
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens


@pytest.mark.django_db
def test_leaving_a_workspace_revokes_its_grants(client, api_client, data_fixture):
    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[admin, user])
    other = data_fixture.create_workspace(user=user)
    kept = obtain_tokens(client, api_client, token, other)
    obtain_tokens(client, api_client, token, workspace)

    CoreHandler().leave_workspace(user, workspace)

    assert list(MCPEndpoint.objects.filter(user=user).values_list("id", flat=True)) == [
        kept["endpoint_id"]
    ]
    assert AccessToken.objects.filter(user=user).count() == 1
    assert RefreshToken.objects.filter(user=user, revoked__isnull=True).count() == 1


@pytest.mark.django_db
def test_removing_a_user_revokes_their_grants(client, api_client, data_fixture):
    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    obtain_tokens(client, api_client, token, workspace)
    workspace_user = workspace.workspaceuser_set.get(user=user)

    CoreHandler().delete_workspace_user(admin, workspace_user)

    assert not MCPEndpoint.objects.filter(user=user).exists()
    assert not AccessToken.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_a_legacy_endpoint_skips_token_lookup(
    data_fixture, django_assert_num_queries
):
    endpoint = data_fixture.create_mcp_endpoint()
    with django_assert_num_queries(0):
        revoke_endpoint_tokens(endpoint)
