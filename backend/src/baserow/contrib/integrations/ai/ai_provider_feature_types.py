from django.db.models import Exists, OuterRef

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.builder.workflow_actions.models import AIAgentWorkflowAction
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

        One service is owned by an automation node or by builder workflow
        actions, and trashing an owner leaves the service row untouched, so a
        service counts only while at least one live owner still reaches it. The
        owner managers already encode which ancestors count as trashed. A
        service whose integration or application is gone belongs to no
        workspace, so the joins drop it from both scopes.

        :param provider_type: The provider type owning the model.
        :param model_identifier: The identifier the services persist.
        :param workspace: The workspace to narrow to, or None for the instance
            scope, which counts every workspace.
        :return: The number of services referencing the model.
        """

        live_automation_owner = Exists(
            AutomationNode.objects.filter(service_id=OuterRef("pk"))
        )
        live_builder_owner = Exists(
            AIAgentWorkflowAction.objects.filter(
                service_id=OuterRef("pk"), page__trashed=False
            )
        )
        queryset = AIAgentService.objects.filter(
            ai_generative_ai_type=provider_type,
            ai_generative_ai_model=model_identifier,
            integration__trashed=False,
            integration__application__trashed=False,
            integration__application__workspace__trashed=False,
        ).filter(live_automation_owner | live_builder_owner)
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
