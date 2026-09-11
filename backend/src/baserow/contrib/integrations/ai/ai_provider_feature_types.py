from django.db.models import Q

from baserow.contrib.integrations.ai.models import AIAgentService
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace


class AIAgentAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_AI_AGENT

    def count_model_references(
        self,
        provider_type: str,
        model_identifier: str,
        workspace: Workspace | None = None,
    ) -> int:
        """
        Count the AI Agent services selecting one provider model.

        One service is owned by an automation node or a builder workflow action,
        and trashing either leaves the service row untouched, so the owners are
        excluded explicitly. A service whose integration or application is gone
        belongs to no workspace, so the joins drop it from both scopes.

        :param provider_type: The provider type owning the model.
        :param model_identifier: The identifier the services persist.
        :param workspace: The workspace to narrow to, or None for the instance
            scope, which counts every workspace.
        :return: The number of services referencing the model.
        """

        queryset = AIAgentService.objects.filter(
            ai_generative_ai_type=provider_type,
            ai_generative_ai_model=model_identifier,
            trashed=False,
            integration__trashed=False,
            integration__application__trashed=False,
            integration__application__workspace__trashed=False,
        ).exclude(
            Q(automation_workflow_node__trashed=True)
            | Q(automation_workflow_node__workflow__trashed=True)
            | Q(aiagentworkflowaction__trashed=True)
            | Q(aiagentworkflowaction__element__trashed=True)
            | Q(aiagentworkflowaction__page__trashed=True)
        )
        if workspace is not None:
            queryset = queryset.filter(integration__application__workspace=workspace)
        return queryset.count()

    def get_workspace_availability(
        self,
        workspace: Workspace | None,
        state: ScopedAIProviderState | None = None,
    ) -> dict[str, bool | dict[str, list[str]]]:
        """
        Return the providers and models available to AI Agent consumers.

        :param workspace: The workspace to resolve, or None for instance scope.
        :param state: Optional provider state already loaded for the same scope.
        :returns: Whether any eligible models exist and their identifiers grouped
            by provider type.
        """

        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=self.type, state=state
        )
        return {"is_enabled": bool(models), "models": models}
