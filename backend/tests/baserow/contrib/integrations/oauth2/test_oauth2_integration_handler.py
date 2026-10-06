from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import signing
from django.test import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.integrations.google.integration_types import (
    GoogleIntegrationType,
)
from baserow.contrib.integrations.oauth2.exceptions import (
    OAuth2IntegrationNotConfigured,
    OAuth2InvalidReturnUrl,
    OAuth2InvalidState,
    OAuth2TokenRequestFailed,
)
from baserow.contrib.integrations.oauth2.handler import (
    STATE_SALT,
    OAuth2IntegrationHandler,
)
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from tests.baserow.contrib.integrations.external_api_test_utils import fake_response

SEND = "baserow.contrib.integrations.oauth2.integration_types.send_http_request"
FRONTEND = "http://localhost:3000"


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND, OAUTH_BACKEND_URL="http://api")
def test_authorization_url_carries_a_signed_state(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(user=user, refresh_token="")

    url = OAuth2IntegrationHandler().get_authorization_url(
        user, integration, f"{FRONTEND}/automation/1/settings"
    )

    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
        GoogleIntegrationType.authorization_url
    )
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["google-client-id"]
    assert params["redirect_uri"] == ["http://api/api/integration/oauth2/callback/"]
    assert params["access_type"] == ["offline"]
    assert params["prompt"] == ["consent"]
    assert "gmail.send" in params["scope"][0]
    state = signing.loads(params["state"][0], salt=STATE_SALT)
    assert state == {
        "integration_id": integration.id,
        "user_id": user.id,
        "return_url": f"{FRONTEND}/automation/1/settings",
    }


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND)
def test_authorization_needs_credentials_a_local_return_url_and_permission(
    data_fixture,
):
    user = data_fixture.create_user()
    handler = OAuth2IntegrationHandler()
    integration = data_fixture.create_google_integration(user=user, client_secret="")
    with pytest.raises(OAuth2IntegrationNotConfigured):
        handler.get_authorization_url(user, integration, f"{FRONTEND}/x")

    integration = data_fixture.create_google_integration(user=user)
    with pytest.raises(OAuth2InvalidReturnUrl):
        handler.get_authorization_url(user, integration, "https://evil.example/x")

    stranger = data_fixture.create_user()
    with pytest.raises(UserNotInWorkspace):
        handler.get_authorization_url(stranger, integration, f"{FRONTEND}/x")


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND, OAUTH_BACKEND_URL="http://api")
def test_callback_stores_the_tokens_and_the_account(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(user=user, refresh_token="")
    handler = OAuth2IntegrationHandler()
    url = handler.get_authorization_url(user, integration, f"{FRONTEND}/back")
    state = parse_qs(urlparse(url).query)["state"][0]

    responses = [
        fake_response(
            200,
            {"access_token": "at", "refresh_token": "rt", "expires_in": 3599},
        ),
        fake_response(200, {"email": "me@example.com"}),
    ]
    with patch(SEND, side_effect=responses) as send:
        return_url = handler.complete_authorization("the-code", state)

    assert return_url == f"{FRONTEND}/back"
    token_call = send.call_args_list[0]
    assert token_call.args[:2] == ("POST", GoogleIntegrationType.token_url)
    assert token_call.kwargs["data"] == {
        "grant_type": "authorization_code",
        "code": "the-code",
        "redirect_uri": "http://api/api/integration/oauth2/callback/",
        "client_id": "google-client-id",
        "client_secret": "google-client-secret",
    }
    integration.refresh_from_db()
    assert integration.refresh_token == "rt"
    assert integration.access_token == "at"
    assert integration.account_email == "me@example.com"
    assert integration.access_token_expires_at > timezone.now() + timedelta(
        seconds=3000
    )


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL=FRONTEND)
def test_callback_refuses_a_bad_state_or_a_refused_code(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(user=user, refresh_token="")
    handler = OAuth2IntegrationHandler()
    with pytest.raises(OAuth2InvalidState):
        handler.complete_authorization("code", "not-a-state")

    state = signing.dumps(
        {"integration_id": integration.id, "user_id": user.id, "return_url": "x"},
        salt=STATE_SALT,
    )
    with patch(
        SEND,
        return_value=fake_response(
            400, {"error": "invalid_grant", "error_description": "Bad code"}
        ),
    ):
        with pytest.raises(OAuth2TokenRequestFailed) as exc:
            handler.complete_authorization("code", state)
    assert "Bad code" in str(exc.value)
    # A first connection must come with a refresh token or it cannot last.
    with patch(SEND, return_value=fake_response(200, {"access_token": "at"})):
        with pytest.raises(OAuth2TokenRequestFailed) as exc:
            handler.complete_authorization("code", state)
    assert "refresh token" in str(exc.value)


@pytest.mark.django_db
def test_access_token_is_cached_refreshed_or_refused(data_fixture):
    user = data_fixture.create_user()
    handler = OAuth2IntegrationHandler()

    integration = data_fixture.create_google_integration(user=user, refresh_token="")
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        handler.get_access_token(integration)

    integration = data_fixture.create_google_integration(
        user=user,
        access_token="fresh",
        access_token_expires_at=timezone.now() + timedelta(minutes=30),
    )
    with patch(SEND) as send:
        assert handler.get_access_token(integration) == "fresh"
    send.assert_not_called()

    integration.access_token_expires_at = timezone.now() + timedelta(seconds=10)
    integration.save()
    with patch(
        SEND, return_value=fake_response(200, {"access_token": "new", "expires_in": 60})
    ) as send:
        assert handler.get_access_token(integration) == "new"
    assert send.call_args.kwargs["data"]["grant_type"] == "refresh_token"
    assert send.call_args.kwargs["data"]["refresh_token"] == "google-refresh-token"
    integration.refresh_from_db()
    assert integration.access_token == "new"
    # Not replaced when the provider sends none back.
    assert integration.refresh_token == "google-refresh-token"

    integration.access_token_expires_at = timezone.now()
    integration.save()
    with patch(SEND, return_value=fake_response(400, {"error": "invalid_grant"})):
        with pytest.raises(RemoteRefusedDispatchException) as exc:
            handler.get_access_token(integration)
    assert "Reconnect" in str(exc.value)


@pytest.mark.django_db
def test_changing_the_app_credentials_disconnects_the_account(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(
        user=user, access_token="at", account_email="me@example.com"
    )
    integration.name = "Renamed"
    integration.save()
    integration.refresh_from_db()
    assert integration.refresh_token == "google-refresh-token"

    integration.client_secret = "another-secret"  # nosec B105
    integration.save()
    integration.refresh_from_db()
    assert integration.refresh_token == ""
    assert integration.access_token == ""
    assert integration.account_email == ""
    assert integration.is_connected is False


@pytest.mark.django_db
def test_oauth2_integration_export_leaves_secrets_out_and_import_copes(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_google_integration(
        user=user, access_token="at", account_email="me@example.com"
    )
    integration_type = integration_type_registry.get("google")
    exported = integration_type.export_serialized(
        integration,
        import_export_config=ImportExportConfig(include_permission_data=False),
    )
    assert exported["client_secret"] is None
    assert exported["refresh_token"] is None
    assert exported["access_token"] is None
    assert exported["client_id"] == "google-client-id"

    imported = integration_type.import_serialized(
        integration.application,
        exported,
        {},
        import_export_config=ImportExportConfig(include_permission_data=False),
    )
    assert imported.client_id == "google-client-id"
    assert imported.client_secret == ""
    assert imported.refresh_token == ""
    assert imported.is_connected is False


@pytest.mark.django_db
def test_oauth2_integration_api_hides_secrets_behind_flags(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_microsoft_integration(
        user=user, account_email="me@example.com", tenant="contoso"
    )
    integration_type = integration_type_registry.get("microsoft")
    serializer = integration_type.get_serializer(integration)
    data = serializer.data
    assert data["has_client_secret"] is True
    assert data["has_refresh_token"] is True
    assert data["account_email"] == "me@example.com"
    assert data["tenant"] == "contoso"
    assert "client_secret" not in data
    assert "refresh_token" not in data
    assert "access_token" not in data
