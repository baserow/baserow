from typing import Optional

from baserow.core.captcha.exceptions import CaptchaProviderDoesNotExist
from baserow.core.registry import Instance, Registry


class CaptchaProviderType(Instance):
    """
    Base class for captcha provider types. Each captcha provider (e.g., Cloudflare
    Turnstile, reCAPTCHA) should extend this class.
    """

    def is_configured(self) -> bool:
        """
        Returns True if all required configuration (env vars, etc.) is present
        for this provider to function.
        """

        raise NotImplementedError(
            "The is_configured method must be implemented by the captcha provider."
        )

    def get_frontend_config(self) -> dict:
        """
        Returns a dict of public configuration to send to the frontend. This must
        not include secrets. For example, a site key but never a secret key.
        """

        raise NotImplementedError(
            "The get_frontend_config method must be implemented by the captcha provider."
        )

    def validate_token(self, token: str, remote_ip: Optional[str] = None) -> bool:
        """
        Validates the captcha response token by calling the provider's verification
        API. Should raise CaptchaVerificationFailed on failure.

        :param token: The captcha response token from the client.
        :param remote_ip: Optional IP address of the client.
        :return: True if validation succeeds.
        :raises CaptchaVerificationFailed: If the token is invalid or verification
            fails.
        """

        raise NotImplementedError(
            "The validate_token method must be implemented by the captcha provider."
        )


class CaptchaProviderRegistry(Registry[CaptchaProviderType]):
    name = "captcha_provider"
    does_not_exist_exception_class = CaptchaProviderDoesNotExist


captcha_provider_registry: CaptchaProviderRegistry = CaptchaProviderRegistry()
