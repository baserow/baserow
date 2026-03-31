from django.test.utils import override_settings

import pytest
import responses

from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.provider_types import (
    TURNSTILE_VERIFY_URL,
    CloudflareTurnstileCaptchaProviderType,
)


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
def test_is_configured():
    provider = CloudflareTurnstileCaptchaProviderType()
    assert provider.is_configured() is True


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="",
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="",
)
def test_is_not_configured_when_keys_empty():
    provider = CloudflareTurnstileCaptchaProviderType()
    assert provider.is_configured() is False


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="",
)
def test_is_not_configured_when_secret_missing():
    provider = CloudflareTurnstileCaptchaProviderType()
    assert provider.is_configured() is False


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
def test_get_frontend_config():
    provider = CloudflareTurnstileCaptchaProviderType()
    config = provider.get_frontend_config()
    assert config == {"site_key": "test-site-key"}


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
@responses.activate
def test_validate_token_success():
    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": True},
        status=200,
    )

    provider = CloudflareTurnstileCaptchaProviderType()
    result = provider.validate_token("valid-token", "1.2.3.4")
    assert result is True

    assert len(responses.calls) == 1
    assert "secret=test-secret-key" in responses.calls[0].request.body
    assert "response=valid-token" in responses.calls[0].request.body
    assert "remoteip=1.2.3.4" in responses.calls[0].request.body


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
@responses.activate
def test_validate_token_without_remote_ip():
    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": True},
        status=200,
    )

    provider = CloudflareTurnstileCaptchaProviderType()
    provider.validate_token("valid-token")

    assert len(responses.calls) == 1
    assert "remoteip" not in responses.calls[0].request.body


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
@responses.activate
def test_validate_token_failure():
    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": False, "error-codes": ["invalid-input-response"]},
        status=200,
    )

    provider = CloudflareTurnstileCaptchaProviderType()
    with pytest.raises(CaptchaVerificationFailed):
        provider.validate_token("invalid-token")


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
@responses.activate
def test_validate_token_network_error():
    """Network errors should bubble up uncaught so they surface in Sentry."""

    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        body=ConnectionError("Connection refused"),
    )

    provider = CloudflareTurnstileCaptchaProviderType()
    with pytest.raises(ConnectionError):
        provider.validate_token("some-token")


@override_settings(
    BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
)
@responses.activate
def test_validate_token_http_500_error():
    """Unexpected HTTP errors should bubble up uncaught so they surface in Sentry."""

    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"error": "internal server error"},
        status=500,
    )

    provider = CloudflareTurnstileCaptchaProviderType()
    with pytest.raises(Exception):
        provider.validate_token("some-token")
