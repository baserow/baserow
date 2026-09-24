from django.conf import settings

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
)
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled


class KumaAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_KUMA
    supports_default_model = True
    required_model_capabilities = (
        AI_PROVIDER_MODEL_CAPABILITY_TEXT,
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    )

    def get_workspace_availability(self, workspace, state=None) -> dict:
        if not feature_flag_is_enabled(FF_AI_PROVIDERS):
            return {
                "is_enabled": bool(settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL),
                "state": "legacy",
            }
        availability = super().get_workspace_availability(workspace, state=state)
        if availability["state"] in {"unconfigured", "invalid"}:
            return {
                "is_enabled": bool(settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL),
                "state": "legacy",
            }
        return availability
