from urllib.parse import parse_qs, urlparse

from django.test import override_settings

import pytest

from baserow.contrib.integrations.microsoft.provider import MicrosoftProvider
from baserow.contrib.integrations.oauth_account.exceptions import (
    AdminConsentRequired,
    ClientRejected,
    OAuthFailed,
    ReconnectRequired,
    SignInCancelled,
    TenantNotAllowed,
)
from baserow.contrib.integrations.oauth_account.providers import (
    OAuthClient,
    TokenSet,
)

from ..oauth_account.fake_provider import FakeResponse
from .utils import ACCOUNT_ID, MICROSOFT_SETTINGS, PROVIDER_REQUEST, TENANT_ID

CLIENT = OAuthClient(client_id="client-id", client_secret="client-secret")  # nosec


def token_set(**claims) -> TokenSet:
    from django.utils import timezone

    return TokenSet(
        access_token="a",  # nosec B106
        refresh_token="r",  # nosec B106
        expires_at=timezone.now(),
        scopes=[],
        claims=claims,
    )


@override_settings(**MICROSOFT_SETTINGS)
def test_the_instance_entra_app_is_the_client():
    provider = MicrosoftProvider()

    assert provider.get_instance_client() == CLIENT
    assert provider.is_configured() is True
    with override_settings(INTEGRATIONS_MICROSOFT_CLIENT_SECRET=""):
        assert provider.get_instance_client() is None
        assert provider.is_configured() is False


@override_settings(**{**MICROSOFT_SETTINGS, "INTEGRATIONS_MICROSOFT_TENANT": "contoso"})
def test_signing_in_goes_to_the_configured_tenant_and_lets_an_account_be_picked():
    provider = MicrosoftProvider()

    authorization = provider.build_authorization(
        CLIENT,
        provider.get_redirect_uri("microsoft"),
        "state",
        provider.normalize_scopes(provider.base_scopes),
        login_hint="alice@contoso.com",
    )

    url = urlparse(authorization.url)
    params = parse_qs(url.query)
    assert url.netloc == "login.microsoftonline.com"
    assert url.path == "/contoso/oauth2/v2.0/authorize"
    assert params["response_mode"] == ["query"]
    assert params["prompt"] == ["select_account"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["login_hint"] == ["alice@contoso.com"]
    assert params["redirect_uri"][0].endswith("/integrations/microsoft/oauth-callback")
    assert "offline_access" in params["scope"][0].split()
    assert provider.get_token_endpoint(CLIENT) == (
        "https://login.microsoftonline.com/contoso/oauth2/v2.0/token"
    )


def test_graph_scopes_are_stored_by_their_short_name_whatever_their_case():
    provider = MicrosoftProvider()

    assert provider.normalize_scopes(
        "https://graph.microsoft.com/Mail.Send mail.send openid User.Read"
    ) == ["Mail.Send", "openid", "User.Read"]
    assert provider.missing_scopes(
        ["chatmessage.send"], ["ChatMessage.Send", "ChannelMessage.Send"]
    ) == ["ChannelMessage.Send"]


def test_the_account_is_read_from_the_id_token():
    identity = MicrosoftProvider().identify(
        CLIENT,
        token_set(
            oid=ACCOUNT_ID,
            tid=TENANT_ID,
            preferred_username="alice@contoso.com",
            name="Alice",
        ),
        deadline=0,
    )

    assert identity.account_id == ACCOUNT_ID
    assert identity.email == "alice@contoso.com"
    assert identity.name == "Alice"
    assert identity.extra == {"tenant_id": TENANT_ID}

    with pytest.raises(OAuthFailed):
        MicrosoftProvider().identify(CLIENT, token_set(tid=TENANT_ID), deadline=0)


@override_settings(**MICROSOFT_SETTINGS)
def test_sign_in_errors_say_what_to_do():
    provider = MicrosoftProvider()
    scopes = ["openid", "ChannelMessage.Send"]

    def classify(error, description):
        return provider.classify_callback_error(error, description, CLIENT, scopes)

    admin = classify("access_denied", "AADSTS90094: Admin consent is required.")
    assert isinstance(admin, AdminConsentRequired)
    url = urlparse(admin.admin_consent_url)
    assert url.path == "/organizations/v2.0/adminconsent"
    consent_scopes = parse_qs(url.query)["scope"][0].split()
    assert "https://graph.microsoft.com/ChannelMessage.Send" in consent_scopes
    assert "openid" in consent_scopes

    assert isinstance(
        classify("invalid_request", "AADSTS50020: User account from identity"),
        TenantNotAllowed,
    )
    assert isinstance(
        classify("access_denied", "AADSTS65004: declined"), SignInCancelled
    )
    assert isinstance(classify("access_denied", ""), SignInCancelled)
    assert isinstance(classify("server_error", "AADSTS1234"), OAuthFailed)


@override_settings(**MICROSOFT_SETTINGS)
def test_refreshing_asks_for_the_granted_scopes_and_reads_entra_errors(mocker):
    provider = MicrosoftProvider()
    request = mocker.patch(
        PROVIDER_REQUEST,
        return_value=FakeResponse(
            200,
            {"access_token": "a", "refresh_token": "r", "expires_in": 3600},
        ),
    )

    provider.refresh(CLIENT, "refresh-token", ["Mail.Send"])

    scope = request.call_args.kwargs["data"]["scope"].split()
    assert {"offline_access", "User.Read", "Mail.Send"} <= set(scope)

    # An expired client secret is the installation's to fix, not the account's.
    mocker.patch(
        PROVIDER_REQUEST,
        return_value=FakeResponse(
            401, {"error": "unauthorized_client", "error_codes": [7000222]}
        ),
    )
    with pytest.raises(ClientRejected):
        provider.refresh(CLIENT, "refresh-token", [])

    mocker.patch(
        PROVIDER_REQUEST,
        return_value=FakeResponse(400, {"error": "invalid_grant", "error_codes": [1]}),
    )
    with pytest.raises(ReconnectRequired):
        provider.refresh(CLIENT, "refresh-token", [])
