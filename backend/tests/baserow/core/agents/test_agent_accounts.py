from datetime import timedelta

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
from baserow.core.agents.handler import AgentHandler
from baserow.core.mcp.auth import INVALID_TOKEN, _resolve_bearer_sync
from baserow.core.user.cache import set_cached_user
from baserow.ws.auth import get_user


@pytest.fixture
def agent_account(data_fixture):
    return data_fixture.create_agent(name="Worker", role_uid="ADMIN")


@pytest.mark.django_db
@pytest.mark.parametrize("cached", [False, True])
def test_agent_cannot_authenticate_with_human_jwt(
    agent_account, api_request_factory, settings, cached
):
    settings.BASEROW_CACHE_TTL_SECONDS = 30
    token = RefreshToken.for_user(agent_account)
    if cached:
        set_cached_user(agent_account)
    request = api_request_factory.get(
        "/", HTTP_AUTHORIZATION=f"JWT {token.access_token}"
    )
    with pytest.raises(AuthenticationFailed):
        JSONWebTokenAuthentication().authenticate(request)
    with pytest.raises(InvalidToken):
        get_user_from_token(str(token), token_class=RefreshToken)
    assert not user_is_valid_for_token(agent_account, token.access_token)


@pytest.mark.django_db
def test_agent_password_login_is_rejected_even_with_a_usable_password(
    agent_account, data_fixture
):
    data_fixture.create_password_provider()
    agent_account.set_password("test-password")
    agent_account.save()
    with pytest.raises(AuthenticationFailed):
        check_user_can_log_in_with_password(agent_account)


@pytest.mark.django_db
def test_agent_cannot_use_human_database_token(
    agent_account, data_fixture, api_request_factory
):
    token = data_fixture.create_token(
        user=agent_account, workspace=AgentHandler.get_workspace(agent_account)
    )
    request = api_request_factory.get("/", HTTP_AUTHORIZATION=f"Token {token.key}")
    with pytest.raises(AuthenticationFailed):
        TokenAuthentication().authenticate(request)


@pytest.mark.django_db
@pytest.mark.parametrize("credential", ["key", "oauth"])
def test_agent_cannot_use_current_human_mcp_credentials(
    agent_account, data_fixture, settings, credential
):
    settings.BASEROW_MCP_OAUTH_ENABLED = True
    workspace = AgentHandler.get_workspace(agent_account)
    if credential == "key":
        endpoint = data_fixture.create_mcp_endpoint(
            user=agent_account, workspace=workspace
        )
        value = endpoint.key
    else:
        client = Application.objects.create(
            name="Test",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        )
        endpoint = data_fixture.create_mcp_endpoint(
            user=agent_account, workspace=workspace, oauth_client_id=client.client_id
        )
        value = "agent-human-oauth-token"
        AccessToken.objects.create(
            user=agent_account,
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
async def test_cached_agent_jwt_is_rejected_by_websockets(agent_account, settings):
    settings.BASEROW_CACHE_TTL_SECONDS = 30
    token = RefreshToken.for_user(agent_account)
    set_cached_user(agent_account)
    assert await get_user(str(token.access_token)) is None
