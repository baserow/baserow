import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.utils import timezone

from baserow.contrib.integrations.oauth_account.exceptions import SignInCancelled
from baserow.contrib.integrations.oauth_account.providers import (
    OAuthClient,
    decode_id_token_claims,
)

from .fake_provider import FakeOAuthProvider, make_id_token

CLIENT = OAuthClient("client-id", "client-secret")


def test_scopes_are_normalized_and_compared_as_the_provider_says():
    provider = FakeOAuthProvider()
    assert provider.normalize_scopes("openid  Mail.Send mail.send ") == [
        "Mail.Send",
        "openid",
    ]
    assert provider.normalize_scopes(["openid", 3, "", None]) == ["openid"]
    assert provider.missing_scopes("mail.send", ["Mail.Send", "Chat.Read"]) == [
        "Chat.Read"
    ]

    provider.scopes_case_sensitive = True
    assert provider.normalize_scopes(["a", "A"]) == ["a", "A"]
    assert provider.missing_scopes(["a"], ["A"]) == ["A"]


def test_id_token_claims_are_read_without_failing_on_garbage():
    assert decode_id_token_claims(make_id_token(sub="x"))["sub"] == "x"
    for garbage in ("", "a", "a.b.c", "a.bm90IGpzb24.c", "a.WzFd.c"):
        assert decode_id_token_claims(garbage) == {}


@override_settings(PUBLIC_WEB_FRONTEND_URL="https://b.io/")
def test_the_authorization_url_uses_pkce_and_the_shared_callback():
    provider = FakeOAuthProvider()

    authorization = provider.build_authorization(
        CLIENT,
        provider.get_redirect_uri("test_oauth"),
        "the-state",
        ["openid"],
        login_hint="alice@example.com",
    )

    params = parse_qs(urlparse(authorization.url).query)
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(authorization.code_verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    assert params["code_challenge"] == [challenge]
    assert params["redirect_uri"] == [
        "https://b.io/integrations/test_oauth/oauth-callback"
    ]
    assert params["state"] == ["the-state"]
    assert params["login_hint"] == ["alice@example.com"]
    assert "client_secret" not in params


def test_client_fingerprints_tell_clients_apart_without_the_secret():
    fingerprint = CLIENT.fingerprint
    assert "client-secret" not in fingerprint
    assert fingerprint == OAuthClient("client-id", "client-secret").fingerprint
    assert fingerprint != OAuthClient("client-id", "other").fingerprint


def test_a_declined_sign_in_is_a_cancellation():
    error = FakeOAuthProvider().classify_callback_error("access_denied", "", CLIENT, [])
    assert isinstance(error, SignInCancelled)


def test_tokens_are_refreshed_before_they_expire():
    provider = FakeOAuthProvider()
    assert provider.expires_soon(None) is True
    assert provider.expires_soon(timezone.now() + timedelta(minutes=2)) is True
    assert provider.expires_soon(timezone.now() + timedelta(hours=1)) is False


def test_the_token_answer_is_parsed_defensively():
    provider = FakeOAuthProvider()
    token_set = provider.parse_token_response(
        {"access_token": "a", "expires_in": "soon", "scope": 3, "refresh_token": 1}
    )
    assert token_set.refresh_token == ""
    assert token_set.scopes == []
    assert token_set.claims == {}
    assert token_set.expires_at > timezone.now() + timedelta(minutes=59)
