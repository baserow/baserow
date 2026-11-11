from django.contrib.auth import get_user_model

import pytest
from oauth2_provider.models import AccessToken, RefreshToken

from baserow.core.admin.users.handler import UserAdminHandler
from baserow.core.handler import CoreHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.tokens import revoke_endpoint_tokens
from baserow.core.user.handler import UserHandler
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens

User = get_user_model()


@pytest.mark.django_db
def test_leaving_a_workspace_revokes_its_grants(client, api_client, data_fixture):
    admin = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[admin, user])
    other = data_fixture.create_workspace(user=user)
    kept = obtain_tokens(client, api_client, token, other, scope="mcp offline_access")
    obtain_tokens(client, api_client, token, workspace, scope="mcp offline_access")

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


@pytest.mark.django_db
def test_permanently_deleting_a_workspace_revokes_its_grants(
    client, api_client, data_fixture
):
    from baserow.core.trash.handler import TrashHandler

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other = data_fixture.create_workspace(user=user)
    obtain_tokens(client, api_client, token, workspace, scope="mcp offline_access")
    kept = obtain_tokens(client, api_client, token, other, scope="mcp offline_access")

    TrashHandler.permanently_delete(workspace)

    assert list(MCPEndpoint.objects.filter(user=user).values_list("id", flat=True)) == [
        kept["endpoint_id"]
    ]
    assert AccessToken.objects.filter(user=user).count() == 1
    assert RefreshToken.objects.filter(user=user).count() == 1


def _change_password(user):
    UserHandler().change_password(user, "password", "new-password-1234")


def _reset_password(user):
    handler = UserHandler()
    token = handler.get_reset_password_signer().dumps(
        [user.id, UserHandler._get_password_state_hash(user)]
    )
    handler.reset_password(token, "new-password-1234")


def _admin_change_password(user):
    admin = User.objects.create_user(
        username="admin@test.nl", email="admin@test.nl", is_staff=True
    )
    UserAdminHandler().update_user(admin, user.id, password="new-password-1234")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change", [_change_password, _reset_password, _admin_change_password]
)
def test_password_change_signs_apps_out(client, api_client, data_fixture, change):
    user, token = data_fixture.create_user_and_token(password="password")
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    other_user, other_token = data_fixture.create_user_and_token()
    obtain_tokens(
        client,
        api_client,
        other_token,
        data_fixture.create_workspace(user=other_user),
    )

    change(user)

    # The grant stays listed, the app has to sign in again.
    assert MCPEndpoint.objects.filter(id=tokens["endpoint_id"]).exists()
    assert not AccessToken.objects.filter(user=user).exists()
    assert not RefreshToken.objects.filter(user=user).exists()
    assert AccessToken.objects.filter(user=other_user).exists()
    refresh = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
        },
    )
    assert refresh.status_code == 400
