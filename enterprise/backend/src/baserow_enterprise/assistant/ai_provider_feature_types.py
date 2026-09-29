from django.conf import settings

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
)
from baserow.core.ai_provider.registries import AIProviderModelFeatureType


class KumaAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_KUMA
    supports_default_model = True
    required_model_capabilities = (
        AI_PROVIDER_MODEL_CAPABILITY_TEXT,
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    )

    def get_workspace_availability(self, workspace, state=None) -> dict:
        """Resolve Kuma availability with the legacy compatibility fallback.

        :param workspace: The workspace whose Kuma availability is requested.
        :param state: Pre-loaded provider state for this scope, if available.
        :returns: Availability from the database selection, or legacy configuration
            when the selection is absent or invalid. Explicit disables are retained.
        """

        availability = super().get_workspace_availability(workspace, state=state)
        if availability["state"] in {"unconfigured", "invalid"}:
            return {
                "is_enabled": bool(settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL),
                "state": "legacy",
            }
        return availability
