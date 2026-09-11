from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_FIELDS
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace
from baserow_premium.fields.models import AIField


class AIFieldsAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_AI_FIELDS

    def count_model_references(
        self,
        provider_type: str,
        model_identifier: str,
        workspace: Workspace | None = None,
    ) -> int:
        """
        Count the AI fields selecting one provider model.

        A field is skipped as soon as any ancestor is trashed, because the whole
        subtree disappears with it.

        :param provider_type: The provider type owning the model.
        :param model_identifier: The identifier the fields persist.
        :param workspace: The workspace to narrow to, or None for the instance
            scope, which counts every workspace.
        :return: The number of fields referencing the model.
        """

        queryset = AIField.objects.filter(
            ai_generative_ai_type=provider_type,
            ai_generative_ai_model=model_identifier,
            trashed=False,
            table__trashed=False,
            table__database__trashed=False,
            table__database__workspace__trashed=False,
        )
        if workspace is not None:
            queryset = queryset.filter(table__database__workspace=workspace)
        return queryset.count()

    def get_workspace_availability(self, workspace, state=None) -> dict:
        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=self.type, state=state
        )
        return {"is_enabled": bool(models), "models": models}
