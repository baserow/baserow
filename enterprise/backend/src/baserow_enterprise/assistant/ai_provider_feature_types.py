from typing import Literal

from django.conf import settings

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderModel
from baserow.core.ai_provider.registries import AIProviderModelFeatureType
from baserow.core.ai_provider.resolution import (
    ScopedAIProviderState,
    get_ai_provider_state,
)
from baserow.core.models import Workspace

KumaModelSource = Literal["database", "legacy", "disabled", "unavailable"]


class KumaAIProviderModelFeatureType(AIProviderModelFeatureType):
    type = AI_PROVIDER_FEATURE_KUMA
    supports_default_model = True
    required_model_capabilities = (
        AI_PROVIDER_MODEL_CAPABILITY_TEXT,
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    )

    def resolve_model(
        self, state: ScopedAIProviderState
    ) -> tuple[AIProviderModel | None, KumaModelSource]:
        """Decide which model Kuma runs on in one scope.

        :param state: The loaded provider state of the scope.
        :return: The usable database model, if any, and the source Kuma resolves
            through. ``legacy`` is the environment model. ``unavailable`` means
            the selection sits on a provider this workspace is excluded from,
            which must not reopen the environment model.
        """

        setting = next(
            value
            for value in AIProviderHandler.list_feature_settings(
                state.workspace, state=state
            )
            if value["feature_type"] == self.type
        )
        if setting["state"] == "disabled":
            return None, "disabled"
        if setting["model"] is not None:
            return setting["model"], "database"
        if self._is_selection_excluded(state):
            return None, "unavailable"
        return None, "legacy"

    def _is_selection_excluded(self, state: ScopedAIProviderState) -> bool:
        selected_setting = state.get_feature_setting(self.type)
        if selected_setting is None and state.workspace is not None:
            selected_setting = state.get_instance_feature_setting(self.type)
        return (
            selected_setting is not None
            and selected_setting.model is not None
            and selected_setting.model.provider_config_id
            in state.excluded_instance_provider_ids
        )

    def get_workspace_availability(
        self,
        workspace: Workspace | None,
        state: ScopedAIProviderState | None = None,
    ) -> dict:
        """Resolve Kuma availability with the legacy compatibility fallback.

        :param workspace: The workspace whose Kuma availability is requested.
        :param state: Pre-loaded provider state for this scope, if available.
        :returns: Availability from the legacy configuration when Kuma resolves
            through it, otherwise from the database selection.
        """

        if state is None:
            state = get_ai_provider_state(workspace)
        _, source = self.resolve_model(state)
        if source == "legacy":
            return {
                "is_enabled": bool(settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL),
                "state": "legacy",
            }
        return super().get_workspace_availability(workspace, state=state)
