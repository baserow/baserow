from typing import Optional

from django.conf import settings

from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.registries import (
    CaptchaProviderType,
    captcha_provider_registry,
)


class CaptchaHandler:
    @staticmethod
    def is_enabled() -> bool:
        """
        Return True if the captcha is enabled in the instance.

        :return: True if captcha is enabled in this instance.
        """

        return bool(getattr(settings, "BASEROW_ENABLE_CAPTCHA", ""))

    @staticmethod
    def is_captcha_enabled_for(context: str) -> bool:
        """
        Returns True if captcha is enabled for the given context.

        :param context: The context to check, e.g. "signup" or "invitations".
        :return: True if captcha should be required for this context.
        """

        if not CaptchaHandler.is_enabled():
            return False

        enabled = getattr(settings, "BASEROW_ENABLE_CAPTCHA", "")
        enabled = enabled.strip().lower()
        if enabled == "all":
            return True

        enabled_contexts = [c.strip().lower() for c in enabled.split(",") if c.strip()]
        return context.lower() in enabled_contexts

    @staticmethod
    def get_active_provider() -> CaptchaProviderType:
        """
        Returns the active captcha provider based on the BASEROW_CAPTCHA_PROVIDER
        setting.

        :raises CaptchaProviderDoesNotExist: If the configured provider type is not
            registered.
        :raises RuntimeError: If the provider is not properly configured (missing
            env vars).
        """

        provider_type = getattr(settings, "BASEROW_CAPTCHA_PROVIDER", "")
        if not provider_type:
            raise RuntimeError(
                "BASEROW_ENABLE_CAPTCHA is set but BASEROW_CAPTCHA_PROVIDER is empty. "
                "Please configure a captcha provider."
            )

        provider = captcha_provider_registry.get(provider_type)

        if not provider.is_configured():
            raise RuntimeError(
                f"Captcha provider '{provider_type}' is enabled but not properly "
                f"configured. Please check that all required environment variables "
                f"are set."
            )

        return provider

    @staticmethod
    def validate_if_required(
        context: str,
        token: str,
        remote_ip: Optional[str] = None,
    ) -> None:
        """
        Validates the captcha token if captcha is enabled for the given context.
        Does nothing if captcha is not enabled.

        :param context: The context to check, e.g. "signup".
        :param token: The captcha response token from the client.
        :param remote_ip: Optional IP address of the client.
        :raises CaptchaVerificationFailed: If captcha is required and the token is
            invalid or missing.
        :raises RuntimeError: If captcha is enabled but not properly configured.
        """

        if not CaptchaHandler.is_captcha_enabled_for(context):
            return

        provider = CaptchaHandler.get_active_provider()

        if not token:
            raise CaptchaVerificationFailed(
                "Captcha token is required but was not provided."
            )

        provider.validate_token(token, remote_ip)
