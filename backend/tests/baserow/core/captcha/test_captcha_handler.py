from django.test.utils import override_settings

import pytest
import responses

from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.handler import CaptchaHandler
from baserow.core.captcha.provider_types import TURNSTILE_VERIFY_URL


def test_is_captcha_enabled_for_all():
    with override_settings(BASEROW_ENABLE_CAPTCHA="all"):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is True
        assert CaptchaHandler.is_captcha_enabled_for("invitations") is True
        assert CaptchaHandler.is_captcha_enabled_for("anything") is True


def test_is_captcha_enabled_for_specific():
    with override_settings(BASEROW_ENABLE_CAPTCHA="signup"):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is True
        assert CaptchaHandler.is_captcha_enabled_for("invitations") is False


def test_is_captcha_enabled_for_multiple():
    with override_settings(BASEROW_ENABLE_CAPTCHA="signup,invitations"):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is True
        assert CaptchaHandler.is_captcha_enabled_for("invitations") is True
        assert CaptchaHandler.is_captcha_enabled_for("other") is False


def test_is_captcha_enabled_case_insensitive():
    with override_settings(BASEROW_ENABLE_CAPTCHA="Signup,INVITATIONS"):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is True
        assert CaptchaHandler.is_captcha_enabled_for("Signup") is True
        assert CaptchaHandler.is_captcha_enabled_for("invitations") is True
        assert CaptchaHandler.is_captcha_enabled_for("INVITATIONS") is True

    with override_settings(BASEROW_ENABLE_CAPTCHA="ALL"):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is True


def test_is_captcha_disabled():
    with override_settings(BASEROW_ENABLE_CAPTCHA=""):
        assert CaptchaHandler.is_captcha_enabled_for("signup") is False
        assert CaptchaHandler.is_captcha_enabled_for("invitations") is False


def test_validate_if_required_skips_when_disabled():
    with override_settings(BASEROW_ENABLE_CAPTCHA=""):
        CaptchaHandler.validate_if_required("signup", "")
        CaptchaHandler.validate_if_required("signup", "some-token")


@pytest.mark.django_db
@responses.activate
def test_validate_if_required_raises_when_token_missing():
    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": True},
        status=200,
    )

    with override_settings(
        BASEROW_ENABLE_CAPTCHA="all",
        BASEROW_CAPTCHA_PROVIDER="cloudflare_turnstile",
        BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
        BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
    ):
        with pytest.raises(CaptchaVerificationFailed):
            CaptchaHandler.validate_if_required("signup", "")

    # No HTTP calls should have been made since token was empty
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_validate_if_required_calls_provider():
    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": True},
        status=200,
    )

    with override_settings(
        BASEROW_ENABLE_CAPTCHA="all",
        BASEROW_CAPTCHA_PROVIDER="cloudflare_turnstile",
        BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
        BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
    ):
        CaptchaHandler.validate_if_required("signup", "valid-token", "1.2.3.4")

    assert len(responses.calls) == 1


@pytest.mark.django_db
def test_validate_if_required_skips_for_unconfigured_context():
    with override_settings(
        BASEROW_ENABLE_CAPTCHA="invitations",
        BASEROW_CAPTCHA_PROVIDER="cloudflare_turnstile",
        BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="test-site-key",
        BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="test-secret-key",
    ):
        # Should not raise since "signup" is not in the enabled contexts
        CaptchaHandler.validate_if_required("signup", "")


@pytest.mark.django_db
def test_get_active_provider_raises_when_provider_not_configured():
    with override_settings(
        BASEROW_ENABLE_CAPTCHA="all",
        BASEROW_CAPTCHA_PROVIDER="cloudflare_turnstile",
        BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY="",
        BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY="",
    ):
        with pytest.raises(RuntimeError, match="not properly configured"):
            CaptchaHandler.get_active_provider()


@pytest.mark.django_db
def test_get_active_provider_raises_when_provider_type_empty():
    with override_settings(
        BASEROW_ENABLE_CAPTCHA="all",
        BASEROW_CAPTCHA_PROVIDER="",
    ):
        with pytest.raises(RuntimeError, match="BASEROW_CAPTCHA_PROVIDER is empty"):
            CaptchaHandler.get_active_provider()
