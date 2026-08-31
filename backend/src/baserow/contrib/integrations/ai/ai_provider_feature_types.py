from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry


class AIAgentAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_AI_AGENT

    def get_workspace_availability(self, workspace, state=None) -> dict:
        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=self.type, state=state
        )
        return {"is_enabled": bool(models), "models": models}
