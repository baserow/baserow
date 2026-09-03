from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.utils import validate_data
from baserow.api.workspaces.serializers import get_generative_ai_settings_serializer
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application


class AIIntegrationType(IntegrationType):
    """
    Integration type for connecting to generative AI providers. Allows users to either
    inherit workspace-level AI settings (default) or override them per integration.
    Explicit overrides are returned here. Otherwise, the database provider resolver
    owns inheritance while that feature is enabled, and legacy workspace JSON remains
    the fallback while it is disabled.
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
        """Validate explicit per-integration provider settings before saving.

        Database-only providers are valid here because these overrides are passed
        directly to the runtime instead of being stored in legacy workspace settings.

        :param values: The integration values supplied by the caller.
        :param user: The user creating or updating the integration.
        :return: The normalized values prepared by the base integration type.
        """

        if "ai_settings" not in values:
            values["ai_settings"] = {}

        if values["ai_settings"]:
            validated_settings = validate_data(
                get_generative_ai_settings_serializer(
                    include_database_only_providers=True
                ),
                values["ai_settings"],
                return_validated=True,
            )
            values["ai_settings"] = validated_settings

        return super().prepare_values(values, user)

    def get_provider_settings(
        self, integration: AIIntegration, provider_type: str
    ) -> Dict[str, Any]:
        """
        Get explicit settings for a provider, or its legacy workspace fallback.

        With database providers enabled, an empty result deliberately tells the
        generative AI model type to resolve the live workspace provider itself.

        :param integration: The AI integration whose provider settings are requested.
        :param provider_type: The generative AI provider type.
        :return: Explicit or legacy provider settings, or an empty dictionary when
            database-backed workspace inheritance should be used.
        """

        # Check if provider has overrides in integration settings
        if provider_type in integration.ai_settings:
            provider_settings = integration.ai_settings[provider_type]
            if isinstance(provider_settings, dict):
                return provider_settings

        if feature_flag_is_enabled(FF_AI_PROVIDERS):
            return {}

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

    def import_serialized(
        self,
        application: Application,
        serialized_values: Dict[str, Any],
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
    ) -> AIIntegration:
        if cache is None:
            cache = {}

        # AI settings are sensitive data, the serialized data will set it `None`.
        serialized_values["ai_settings"] = serialized_values["ai_settings"] or {}

        return super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def export_serialized(
        self,
        instance: AIIntegration,
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Export the AI integration, materializing inherited legacy settings if needed.

        Published applications recover their original workspace at dispatch time when
        database providers are enabled, so only legacy JSON settings need to be copied.

        :param instance: The integration to export.
        :param import_export_config: Export behavior, including publishing state.
        :param files_zip: Optional archive receiving exported files.
        :param storage: Optional storage backend.
        :param cache: Optional export cache.
        :return: The serialized integration values.
        """

        serialized = super().export_serialized(
            instance,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

        # Legacy published applications cannot recover workspace JSON at dispatch
        # time, so materialize it while that resolver is still in use.
        if (
            import_export_config
            and import_export_config.is_publishing
            and not feature_flag_is_enabled(FF_AI_PROVIDERS)
        ):
            workspace = instance.application.workspace
            if workspace and workspace.generative_ai_models_settings:
                materialized_settings = dict(serialized.get("ai_settings", {}))
                for (
                    provider_type,
                    workspace_provider_settings,
                ) in workspace.generative_ai_models_settings.items():
                    if provider_type not in materialized_settings:
                        materialized_settings[provider_type] = (
                            workspace_provider_settings
                        )

                serialized["ai_settings"] = materialized_settings

        return serialized
