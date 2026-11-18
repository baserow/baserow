from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest
from oauth2_provider.models import AccessToken, Application
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.api.authentication import JSONWebTokenAuthentication
from baserow.api.user.jwt import get_user_from_token, user_is_valid_for_token
from baserow.api.user.serializers import check_user_can_log_in_with_password
from baserow.contrib.database.api.tokens.authentications import TokenAuthentication
from baserow.core.identities.handler import IdentityHandler
from baserow.core.mcp.auth import INVALID_TOKEN, _resolve_bearer_sync
from baserow.core.models import User
from baserow.core.user.cache import set_cached_user
from baserow.ws.auth import get_user


@pytest.fixture
def identity_account(data_fixture):
    return data_fixture.create_identity(name="Worker", role_uid="ADMIN")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind,cached,expected_status",
    [
        ("human", False, 200),
        ("human", True, 200),
        ("identity", False, 401),
        ("identity", True, 401),
        ("unknown", False, 401),
        ("unknown", True, 401),
        ("stale_profile", True, 200),
        ("anonymous", False, 401),
    ],
)
def test_identity_creation_api_requires_a_current_human_profile(
    data_fixture, api_client, settings, kind, cached, expected_status
):
    settings.BASEROW_CACHE_TTL_SECONDS = 30
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    if kind == "identity":
        user = data_fixture.create_identity(workspace=workspace, role_uid="ADMIN")
    elif kind == "unknown":
        user.profile.user_type = "unknown"
        user.profile.save(update_fields=["user_type"])
    elif kind == "stale_profile":
        del user.profile.__dict__["user_type"]
    if cached:
        set_cached_user(user)
    headers = (
        {}
        if kind == "anonymous"
        else {"HTTP_AUTHORIZATION": f"JWT {RefreshToken.for_user(user).access_token}"}
    )
    users_before = User.objects_and_identities.count()

    response = api_client.post(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"name": "Created by a user"},
        format="json",
        **headers,
    )

    assert response.status_code == expected_status
    assert User.objects_and_identities.count() == users_before + (
        expected_status == 200
    )


@pytest.mark.django_db
def test_identity_password_login_api_does_not_issue_tokens(
    identity_account, data_fixture, api_client
):
    data_fixture.create_password_provider()
    identity_account.set_password("identity-test-password")
    identity_account.save(update_fields=["password"])

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": identity_account.email, "password": "identity-test-password"},
        format="json",
    )

    assert response.status_code == 401
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    identity_account.refresh_from_db()
    assert identity_account.last_login is None


@pytest.mark.django_db
@pytest.mark.parametrize("cached", [False, True])
def test_identity_cannot_authenticate_with_human_jwt(
    identity_account, api_request_factory, settings, cached
):
    settings.BASEROW_CACHE_TTL_SECONDS = 30
    token = RefreshToken.for_user(identity_account)
    if cached:
        set_cached_user(identity_account)
    request = api_request_factory.get(
        "/", HTTP_AUTHORIZATION=f"JWT {token.access_token}"
    )
    with pytest.raises(AuthenticationFailed):
        JSONWebTokenAuthentication().authenticate(request)
    with pytest.raises(InvalidToken):
        get_user_from_token(str(token), token_class=RefreshToken)
    assert not user_is_valid_for_token(identity_account, token.access_token)


@pytest.mark.django_db
def test_identity_password_login_is_rejected_even_with_a_usable_password(
    identity_account, data_fixture
):
    data_fixture.create_password_provider()
    identity_account.set_password("test-password")
    identity_account.save()
    with pytest.raises(AuthenticationFailed):
        check_user_can_log_in_with_password(identity_account)


@pytest.mark.django_db
def test_identity_cannot_use_human_database_token(
    identity_account, data_fixture, api_request_factory
):
    token = data_fixture.create_token(
        user=identity_account, workspace=IdentityHandler.get_workspace(identity_account)
    )
    request = api_request_factory.get("/", HTTP_AUTHORIZATION=f"Token {token.key}")
    with pytest.raises(AuthenticationFailed):
        TokenAuthentication().authenticate(request)


@pytest.mark.django_db
@pytest.mark.parametrize("credential", ["key", "oauth"])
def test_identity_cannot_use_current_human_mcp_credentials(
    identity_account, data_fixture, settings, credential
):
    settings.BASEROW_MCP_OAUTH_ENABLED = True
    workspace = IdentityHandler.get_workspace(identity_account)
    if credential == "key":
        endpoint = data_fixture.create_mcp_endpoint(
            user=identity_account, workspace=workspace
        )
        value = endpoint.key
    else:
        client = Application.objects.create(
            name="Test",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        )
        endpoint = data_fixture.create_mcp_endpoint(
            user=identity_account, workspace=workspace, oauth_client_id=client.client_id
        )
        value = "identity-human-oauth-token"
        AccessToken.objects.create(
            user=identity_account,
            application=client,
            token=value,
            expires=timezone.now() + timedelta(hours=1),
            scope=f"mcp endpoint:{endpoint.id}",
            resource=[settings.MCP_RESOURCE_URL],
        )
    assert _resolve_bearer_sync(value) == (None, INVALID_TOKEN)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_cached_identity_jwt_is_rejected_by_websockets(
    identity_account, settings
):
    settings.BASEROW_CACHE_TTL_SECONDS = 30
    token = RefreshToken.for_user(identity_account)
    set_cached_user(identity_account)
    assert await get_user(str(token.access_token)) is None
