from django.http import HttpRequest

from baserow.api.settings.registries import SettingsDataType
from baserow.core.captcha.handler import CaptchaHandler


class CaptchaSettingsDataType(SettingsDataType):
    type = "captcha"

    def get_settings_data(self, request: HttpRequest) -> dict:
        disabled = {"enabled": False}

        if not CaptchaHandler.is_enabled():
            return disabled

        provider = CaptchaHandler.get_active_provider()
        if provider is None:
            return disabled

        enabled_contexts = [
            ctx for ctx in ["signup"] if CaptchaHandler.is_captcha_enabled_for(ctx)
        ]

        if not enabled_contexts:
            return disabled

        return {
            "enabled": True,
            "provider": provider.type,
            "enabled_contexts": enabled_contexts,
            **provider.get_frontend_config(),
        }
