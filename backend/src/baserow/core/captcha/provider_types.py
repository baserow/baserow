import logging
from typing import Optional

from django.conf import settings

import requests

from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.registries import CaptchaProviderType

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CloudflareTurnstileCaptchaProviderType(CaptchaProviderType):
    type = "cloudflare_turnstile"

    def is_configured(self) -> bool:
        return bool(
            getattr(settings, "BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY", "")
            and getattr(settings, "BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY", "")
        )

    def get_frontend_config(self) -> dict:
        return {
            "site_key": getattr(settings, "BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY", ""),
        }

    def validate_token(self, token: str, remote_ip: Optional[str] = None) -> bool:
        secret_key = getattr(settings, "BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY", "")

        payload = {
            "secret": secret_key,
            "response": token,
        }

        if remote_ip:
            payload["remoteip"] = remote_ip

        # Let network errors and unexpected HTTP errors bubble up uncaught so they
        # surface in Sentry. Only expected captcha failures are caught below.
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            logger.warning("Cloudflare Turnstile verification failed: %s", error_codes)
            raise CaptchaVerificationFailed("Captcha verification failed.")

        return True
