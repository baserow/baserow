from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.utils import validate_data
from baserow.api.workspaces.serializers import get_generative_ai_settings_serializer
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict


class AIIntegrationType(IntegrationType):
    """
    Integration type for connecting to generative AI providers. Allows users to either
    inherit workspace-level AI settings (default) or override them per integration. If
    a provider key is not present in ai_settings, it inherits from workspace settings.
    If present, it overrides with the specified values.
    """

    type = "ai"
    model_class = AIIntegration

    class SerializedDict(IntegrationDict):
        ai_settings: Dict[str, Any]

    serializer_field_names = ["ai_settings"]
    allowed_fields = ["ai_settings"]
    sensitive_fields = ["ai_settings"]

    serializer_field_overrides = {
        "ai_settings": serializers.JSONField(
            required=False,
            default=dict,
            help_text="Per-provider AI settings overrides. If a provider key is not "
            "present, workspace settings are inherited. If present, these values "
            "override workspace settings. Structure: "
            '{"openai": {"api_key": "...", "models": [...], "organization": ""}, ...}',
        ),
    }

    request_serializer_field_names = ["ai_settings"]
    request_serializer_field_overrides = {
        "ai_settings": serializers.JSONField(required=False, default=dict),
    }

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        """
        Prepare and validate the AI settings before saving. Uses the same validation as
        workspace-level AI settings. Converts comma-separated models strings to arrays.
        """

        if "ai_settings" not in values:
            values["ai_settings"] = {}

        # Validate ai_settings using the same serializer as workspace settings
        # because it should allow to override the same settings.
        if values["ai_settings"]:
            validated_settings = validate_data(
                get_generative_ai_settings_serializer(),
                values["ai_settings"],
                return_validated=True,
            )
            values["ai_settings"] = validated_settings

        return super().prepare_values(values, user)

    def get_provider_settings(
        self, integration: AIIntegration, provider_type: str
    ) -> Dict[str, Any]:
        """
        Get all settings for a specific provider, either from integration
        settings or from workspace settings as fallback.
        """

        # Check if provider has overrides in integration settings
        if provider_type in integration.ai_settings:
            provider_settings = integration.ai_settings[provider_type]
            if isinstance(provider_settings, dict):
                return provider_settings

        # Fall back to workspace settings
        workspace = integration.application.workspace
        if workspace is None:
            return {}
        workspace_settings = workspace.generative_ai_models_settings or {}
        return workspace_settings.get(provider_type, {})

    def is_provider_overridden(
        self, integration: AIIntegration, provider_type: str
    ) -> bool:
        """
        Check if a provider is overridden in the integration settings.
        """

        return provider_type in integration.ai_settings

    def export_serialized(
        self,
        instance: AIIntegration,
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Export the AI integration with materialized settings. When publishing, copy
        workspace-level AI settings into the integration so it doesn't depend on
        workspace (which will be None in published workflows).
        """

        serialized = super().export_serialized(
            instance,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

        # When publishing (is_publishing=True), materialize workspace settings into the
        # integration so published workflows don't lose access to settings. This is
        # because the published workflow does not have access to the workspace.
        if import_export_config and import_export_config.is_publishing:
            workspace = instance.application.workspace
            if workspace and workspace.generative_ai_models_settings:
                materialized_settings = dict(serialized.get("ai_settings", {}))
                for (
                    provider_type,
                    workspace_provider_settings,
                ) in workspace.generative_ai_models_settings.items():
                    if provider_type not in materialized_settings:
                        materialized_settings[
                            provider_type
                        ] = workspace_provider_settings

                serialized["ai_settings"] = materialized_settings

        return serialized
