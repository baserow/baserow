from baserow.core.registry import Instance, Registry

from .constants import (
    AI_PROVIDER_MODEL_CAPABILITIES,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
)
from .exceptions import AIProviderModelFeatureTypeDoesNotExist


class AIProviderModelFeatureType(Instance):
    """A Baserow feature for which an AI provider model can be available."""

    supports_default_model = False
    required_model_capabilities = (AI_PROVIDER_MODEL_CAPABILITY_TEXT,)

    def get_workspace_availability(self, workspace, state=None) -> dict:
        """Return the client-facing effective availability for this feature.

        :param workspace: The workspace scope, or None for the instance scope.
        :param state: An already-loaded state for the scope, avoiding a reload.
        :return: ``is_enabled`` plus, for default-model features, the resolved
            ``state`` the scope ended up in.
        """

        if not self.supports_default_model:
            return {"is_enabled": True}

        from .handler import AIProviderHandler

        setting = next(
            value
            for value in AIProviderHandler.list_feature_settings(workspace, state=state)
            if value["feature_type"] == self.type
        )
        return {
            "is_enabled": setting["state"] in {"configured", "inherited", "overridden"},
            "state": setting["state"],
        }


class AIProviderModelFeatureTypeRegistry(Registry[AIProviderModelFeatureType]):
    name = "ai_provider_model_feature_type"
    does_not_exist_exception_class = AIProviderModelFeatureTypeDoesNotExist

    def get_default_model_feature_types(self) -> list[str]:
        """Return features which expose one scoped default-model setting."""

        return [
            feature_type.type
            for feature_type in self.get_all()
            if feature_type.supports_default_model
        ]

    def get_required_model_capabilities(self, feature_types: list[str]) -> list[str]:
        """Return the ordered capabilities needed by the selected features.

        :param feature_types: The persisted feature identifiers of one model, which
            may name a feature no longer registered by this installation.
        :return: The capabilities the model must pass, always including text.
        """

        required = {AI_PROVIDER_MODEL_CAPABILITY_TEXT}
        for feature_type in feature_types:
            # Feature identifiers are persisted in JSON and can outlive an
            # optional plugin registration (for example after switching to an
            # OSS-only installation). Keep those models testable using the
            # baseline text probe. Explicit API writes are still validated by
            # ``AIProviderHandler._normalize_feature_types``.
            feature = self.registry.get(feature_type)
            if feature is not None:
                required.update(feature.required_model_capabilities)
        return [
            capability
            for capability in AI_PROVIDER_MODEL_CAPABILITIES
            if capability in required
        ]

    def get_feature_test_results(
        self,
        feature_types: list[str],
        capability_results: dict[str, dict],
    ) -> list[dict]:
        """Derive user-facing feature results from reusable capability probes.

        :param feature_types: The features the tested model is eligible for.
        :param capability_results: The per-capability probe outcome of that model.
        :return: One entry per feature, failing when a capability it needs failed.
        """

        results = []
        for feature_type in feature_types:
            feature = self.registry.get(feature_type)
            required_capabilities = (
                feature.required_model_capabilities
                if feature is not None
                else (AI_PROVIDER_MODEL_CAPABILITY_TEXT,)
            )
            failed = [
                capability_results.get(capability, {})
                for capability in required_capabilities
                if capability_results.get(capability, {}).get("status") != "success"
            ]
            results.append(
                {
                    "feature_type": feature_type,
                    "status": "failure" if failed else "success",
                    "error": next(
                        (
                            result.get("error", "")
                            for result in failed
                            if result.get("error")
                        ),
                        "",
                    ),
                }
            )
        return results

    def get_workspace_availability(self, workspace, state=None) -> dict[str, dict]:
        """Return the effective availability of every feature in one scope.

        :param workspace: The workspace scope, or None for the instance scope.
        :param state: An already-loaded state for the scope, avoiding a reload.
        :return: The per-feature availability, keyed by feature type.
        """

        from .resolution import get_ai_provider_state

        if state is None:
            state = get_ai_provider_state(workspace)
        return {
            feature_type.type: feature_type.get_workspace_availability(
                workspace, state=state
            )
            for feature_type in self.get_all()
        }


ai_provider_model_feature_type_registry = AIProviderModelFeatureTypeRegistry()
