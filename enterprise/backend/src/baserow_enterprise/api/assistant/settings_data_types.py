from baserow.api.settings.registries import SettingsDataType
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_KUMA
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)


class KumaSettingsDataType(SettingsDataType):
    type = "kuma"

    def get_settings_data(self, request) -> dict:
        feature_type = ai_provider_model_feature_type_registry.get(
            AI_PROVIDER_FEATURE_KUMA
        )
        availability = feature_type.get_workspace_availability(None)
        return {"is_enabled": availability["is_enabled"]}
