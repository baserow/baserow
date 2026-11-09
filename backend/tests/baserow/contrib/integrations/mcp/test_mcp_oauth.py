import asyncio
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

import pytest
from asgiref.sync import async_to_sync
from freezegun import freeze_time

from baserow.contrib.integrations.mcp import oauth
from baserow.contrib.integrations.mcp.exceptions import (
    MCPOAuthFailed,
    MCPServerNotConnected,
)
from baserow.contrib.integrations.mcp.handler import MCPServerHandler
from baserow.contrib.integrations.mcp.models import MCPServerIntegration
from baserow.core.integrations.service import IntegrationService

from .utils import FakeAuthorizationServer, make_server, serve, serve_oauth


def oauth_server(data_fixture, user, **kwargs):
    return data_fixture.create_mcp_server_integration(
        user=user, url=FakeAuthorizationServer.SERVER_URL, auth_type="oauth", **kwargs
    )


def start(api_client, token, integration):
    return api_client.post(
        reverse("api:mcp_server:oauth_start", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


def complete(api_client, token, state, code=""):
    # Sent by the frontend page the provider redirects the editor back to.
    return api_client.post(
        reverse("api:mcp_server:oauth_complete"),
        {"state": state, "code": code},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_connecting_registers_baserow_and_stores_the_tokens(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    opened = serve(mocker, make_server())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)

    response = start(api_client, token, integration)

    assert response.status_code == 200, response.json()
    url = response.json()["authorization_url"]
    params = parse_qs(urlparse(url).query)
    assert url.startswith(f"{FakeAuthorizationServer.ISSUER}/authorize?")
    assert params["client_id"] == ["registered-client"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["resource"] == [FakeAuthorizationServer.SERVER_URL]
    assert params["scope"] == ["read write"]
    assert params["redirect_uri"][0].endswith("/agent/mcp-oauth-callback")

    response = complete(
        api_client, token, state=params["state"][0], code=fake.authorize(url)
    )

    assert response.status_code == 200, response.json()
    assert response.json()["oauth_connected"] is True
    integration.refresh_from_db()
    assert integration.oauth_access_token == "access-1"
    assert integration.oauth_connected_by_id == user.id

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["oauth_connected"] is True
    assert body["oauth_client_source"] == "dynamic"
    assert "access-1" not in str(body) and "refresh-1" not in str(body)
    assert opened[-1].headers == {"Authorization": "Bearer access-1"}


@pytest.mark.django_db
def test_a_callback_state_works_once_and_only_for_its_authorization(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    assert complete(api_client, token, state="forged", code="x").status_code == 400
    assert (
        complete(api_client, token, state=state, code=fake.authorize(url)).status_code
        == 200
    )
    # Replaying the redirect doesn't connect again.
    assert (
        complete(api_client, token, state=state, code=fake.authorize(url)).status_code
        == 400
    )
    integration.refresh_from_db()
    assert integration.oauth_access_token == "access-1"


@pytest.mark.django_db
def test_only_the_editor_who_started_a_sign_in_can_finish_it(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    # Someone else, even in the same workspace, opens the editor's sign-in link.
    other, other_token = data_fixture.create_user_and_token(
        workspace=integration.application.workspace
    )
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    response = complete(api_client, other_token, state=state, code=fake.authorize(url))

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_OAUTH_STATE_INVALID"
    integration.refresh_from_db()
    assert not integration.oauth_connected
    # Their attempt doesn't use up the editor's sign-in.
    response = complete(api_client, token, state=state, code=fake.authorize(url))
    assert response.status_code == 200, response.json()


@pytest.mark.django_db
def test_a_cancelled_sign_in_stores_nothing(data_fixture, api_client, mocker):
    serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    response = complete(api_client, token, state=state)

    assert response.status_code == 400
    assert "cancelled" in response.json()["detail"]
    integration.refresh_from_db()
    assert not integration.oauth_connected


@pytest.mark.django_db
def test_an_editor_can_enter_their_own_client(data_fixture, api_client, mocker):
    fake = serve_oauth(mocker, FakeAuthorizationServer(registration=False))
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    integration = (
        IntegrationService()
        .update_integration(
            user, integration, oauth_client_id="my-client", oauth_client_secret="shh"
        )
        .integration
    )
    assert integration.oauth_client_source == "manual"

    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    complete(api_client, token, state=state, code=fake.authorize(url))

    token_request = fake.requests[-1]
    form = parse_qs(token_request.content.decode())
    assert form["client_id"] == ["my-client"]
    assert form["client_secret"] == ["shh"]
    assert not any(str(r.url).endswith("/register") for r in fake.requests)


@pytest.mark.django_db
def test_a_server_without_registration_asks_for_a_client(
    data_fixture, api_client, mocker
):
    serve_oauth(mocker, FakeAuthorizationServer(registration=False))
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)

    response = start(api_client, token, integration)

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_OAUTH_FAILED"
    assert "client id" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    PUBLIC_BACKEND_URL="https://api.baserow.example.com",
    PUBLIC_WEB_FRONTEND_URL="https://baserow.example.com",
)
def test_https_instances_use_their_client_metadata_document(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer(metadata_document=True))
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)

    url = start(api_client, token, integration).json()["authorization_url"]

    metadata_url = (
        "https://api.baserow.example.com/api/integrations/mcp/oauth/"
        "client-metadata.json"
    )
    assert parse_qs(urlparse(url).query)["client_id"] == [metadata_url]
    assert not any(str(r.url).endswith("/register") for r in fake.requests)
    document = api_client.get(reverse("api:mcp_server:oauth_client_metadata")).json()
    assert document["client_id"] == metadata_url
    assert document["redirect_uris"] == [
        "https://baserow.example.com/agent/mcp-oauth-callback"
    ]


@pytest.mark.django_db
def test_an_expiring_token_is_refreshed_and_a_refused_one_disconnects(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    complete(api_client, token, state=state, code=fake.authorize(url))
    integration.refresh_from_db()
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_expires_at=timezone.now() + timedelta(seconds=30)
    )
    integration.refresh_from_db()

    connection = MCPServerHandler().get_connection(integration)

    assert connection.headers == {"Authorization": "Bearer access-2"}
    integration.refresh_from_db()
    assert integration.oauth_access_token == "access-2"

    fake.refresh_fails = True
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_expires_at=timezone.now()
    )
    integration.refresh_from_db()
    with pytest.raises(MCPServerNotConnected):
        MCPServerHandler().get_connection(integration)
    integration.refresh_from_db()
    assert not integration.oauth_connected


@pytest.mark.django_db
def test_an_unavailable_authorization_server_keeps_the_account(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    complete(api_client, token, state=state, code=fake.authorize(url))
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_expires_at=timezone.now()
    )
    integration.refresh_from_db()
    fake.refresh_unavailable = True

    with pytest.raises(MCPServerNotConnected):
        MCPServerHandler().get_connection(integration)

    integration.refresh_from_db()
    assert integration.oauth_refresh_token == "refresh-1"
    fake.refresh_unavailable = False
    connection = MCPServerHandler().get_connection(integration)
    assert connection.headers == {"Authorization": "Bearer access-2"}


@pytest.mark.django_db
def test_an_unconnected_server_cant_list_tools(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_SERVER_NOT_CONNECTED"


@pytest.mark.django_db
def test_a_new_url_forgets_the_account_and_the_registered_client(data_fixture):
    user = data_fixture.create_user()
    integration = oauth_server(
        data_fixture,
        user,
        oauth_client_id="registered-client",
        oauth_client_source="dynamic",
        oauth_access_token="access-1",
        oauth_refresh_token="refresh-1",
    )

    integration = (
        IntegrationService()
        .update_integration(user, integration, url="https://other.example.com/mcp")
        .integration
    )

    integration.refresh_from_db()
    assert not integration.oauth_connected
    assert integration.oauth_refresh_token == ""
    assert integration.oauth_client_id == ""


@pytest.mark.django_db
def test_exports_leave_out_tokens_and_registered_clients(data_fixture):
    user = data_fixture.create_user()
    integration = oauth_server(
        data_fixture,
        user,
        oauth_client_id="registered-client",
        oauth_client_source="dynamic",
        oauth_access_token="access-1",
        oauth_refresh_token="refresh-1",
    )

    exported = integration.get_type().export_serialized(integration)

    assert exported["auth_type"] == "oauth"
    assert exported["oauth_client_id"] == ""
    assert "access-1" not in str(exported) and "refresh-1" not in str(exported)


@pytest.mark.django_db
def test_a_sign_in_started_before_the_server_moved_cant_finish(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer(registration=False))
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(
        data_fixture,
        user,
        oauth_client_id="my-client",
        oauth_client_source="manual",
        oauth_client_secret="shh",
    )
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    IntegrationService().update_integration(
        user,
        integration,
        url="https://other.example.com/mcp",
        oauth_client_secret="shh",
    )

    response = complete(api_client, token, state=state, code=fake.authorize(url))

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_OAUTH_STATE_INVALID"


@pytest.mark.django_db
def test_a_token_without_a_lifetime_is_still_refreshed(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    fake.expires_in = None
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    complete(api_client, token, state=state, code=fake.authorize(url))

    with freeze_time(timezone.now() + timedelta(days=1)):
        connection = MCPServerHandler().get_connection(
            MCPServerIntegration.objects.get(id=integration.id)
        )

    # Providers may leave the lifetime out; the token is refreshed anyway.
    assert connection.headers == {"Authorization": "Bearer access-2"}


@pytest.mark.django_db
def test_a_token_without_a_refresh_token_is_used_until_it_expires(data_fixture):
    user = data_fixture.create_user()
    integration = oauth_server(
        data_fixture,
        user,
        oauth_access_token="access-1",
        oauth_expires_at=timezone.now() + timedelta(seconds=60),
    )

    connection = MCPServerHandler().get_connection(integration)

    assert connection.headers == {"Authorization": "Bearer access-1"}
    integration.oauth_expires_at = timezone.now() - timedelta(seconds=1)
    with pytest.raises(MCPServerNotConnected):
        MCPServerHandler().get_connection(integration)
    integration.refresh_from_db()
    # Shown as not connected, so editors are asked to sign in again.
    assert not integration.oauth_connected


def test_a_token_endpoint_that_never_answers_times_out(mocker):
    async def forever(*args, **kwargs):
        await asyncio.sleep(3600)

    client = mocker.MagicMock()
    client.__aenter__.return_value.post = forever
    mocker.patch(
        "baserow.contrib.integrations.mcp.oauth.create_mcp_http_client",
        return_value=client,
    )
    mocker.patch("baserow.contrib.integrations.mcp.oauth.OAUTH_REQUEST_DEADLINE", 0.05)
    server = oauth.OAuthServer(
        issuer="https://auth.example.com",
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )
    client_info = oauth.OAuthClient("id", "", "dynamic", "none")

    with pytest.raises(MCPOAuthFailed) as error:
        async_to_sync(oauth.refresh)(server, client_info, "refresh-1")
    assert error.value.retryable


@pytest.mark.django_db
def test_a_new_sign_in_never_keeps_the_previous_accounts_refresh_token(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    fake.refresh_token = None
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(
        data_fixture, user, oauth_access_token="a", oauth_refresh_token="previous"
    )
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    complete(api_client, token, state=state, code=fake.authorize(url))

    integration.refresh_from_db()
    assert integration.oauth_access_token == "access-1"
    assert integration.oauth_refresh_token == ""


@pytest.mark.django_db
def test_a_secret_added_to_your_own_client_is_used_from_the_next_refresh(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer(registration=False))
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    service = IntegrationService()
    integration = service.update_integration(
        user, integration, oauth_client_id="my-client"
    ).integration
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    complete(api_client, token, state=state, code=fake.authorize(url))
    integration.refresh_from_db()

    # The provider now wants a secret, and the editor adds it.
    integration = service.update_integration(
        user, integration, oauth_client_secret="shh"
    ).integration
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_expires_at=timezone.now()
    )
    integration.refresh_from_db()
    MCPServerHandler().get_connection(integration)

    form = parse_qs(fake.requests[-1].content.decode())
    assert form["grant_type"] == ["refresh_token"]
    assert form["client_secret"] == ["shh"]


@pytest.mark.django_db
def test_a_server_moved_during_the_token_exchange_gets_no_tokens(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    exchange = oauth.exchange_code

    async def exchange_while_moved(*args, **kwargs):
        # Another editor saves a new URL while the provider answers.
        await MCPServerIntegration.objects.filter(id=integration.id).aupdate(
            url="https://other.example.com/mcp"
        )
        return await exchange(*args, **kwargs)

    mocker.patch.object(oauth, "exchange_code", exchange_while_moved)

    response = complete(api_client, token, state=state, code=fake.authorize(url))

    assert response.status_code == 400
    integration.refresh_from_db()
    assert integration.oauth_access_token == ""


@pytest.mark.django_db
def test_an_expired_token_is_cleared_without_undoing_a_new_sign_in(data_fixture):
    integration = oauth_server(
        data_fixture,
        data_fixture.create_user(),
        oauth_access_token="access-1",
        oauth_expires_at=timezone.now() - timedelta(seconds=1),
    )
    # An editor signs in again after the reply read the server.
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_access_token="access-2",
        oauth_expires_at=timezone.now() + timedelta(hours=1),
    )

    with pytest.raises(MCPServerNotConnected):
        MCPServerHandler().get_connection(integration)

    integration.refresh_from_db()
    assert integration.oauth_access_token == "access-2"


@pytest.mark.django_db
def test_a_registered_secret_is_sent_when_the_server_doesnt_say_how(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    fake.confidential = True
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)
    url = start(api_client, token, integration).json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]

    complete(api_client, token, state=state, code=fake.authorize(url))

    # RFC 7591: without a method, a client with a secret uses Basic auth.
    assert fake.requests[-1].headers["Authorization"].startswith("Basic ")


@pytest.mark.django_db
def test_an_unreachable_metadata_url_falls_back_to_the_next(
    data_fixture, api_client, mocker
):
    fake = serve_oauth(mocker, FakeAuthorizationServer())
    fake.unreachable_metadata_url = "https://down.example.com/metadata"
    user, token = data_fixture.create_user_and_token()
    integration = oauth_server(data_fixture, user)

    response = start(api_client, token, integration)

    assert response.status_code == 200, response.json()
