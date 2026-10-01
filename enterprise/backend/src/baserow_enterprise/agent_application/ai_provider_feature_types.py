from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_AGENT_BUILDER,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
)
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace
from baserow_enterprise.agent_application.models import AgentDefinition


class AgentBuilderAIProviderModelFeatureType(AIProviderModelFeatureType):
    """
    Agent applications run a tool-calling loop, so only models with tool
    support are eligible. Every agent stores its own provider type and model
    identifier, like AI fields and AI Agent nodes do.
    """

    type = AI_PROVIDER_FEATURE_AGENT_BUILDER
    required_model_capabilities = (
        AI_PROVIDER_MODEL_CAPABILITY_TEXT,
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    )

    def count_model_references(
        self,
        provider_type: str,
        model_identifier: str,
        workspace: Workspace | None = None,
    ) -> int:
        queryset = AgentDefinition.objects.filter(
            ai_generative_ai_type=provider_type,
            ai_generative_ai_model=model_identifier,
            application__trashed=False,
            application__workspace__trashed=False,
        )
        if workspace is not None:
            queryset = queryset.filter(application__workspace=workspace)
        return queryset.count()

    def get_workspace_availability(self, workspace, state=None) -> dict:
        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=self.type, state=state
        )
        return {"is_enabled": bool(models), "models": models}
