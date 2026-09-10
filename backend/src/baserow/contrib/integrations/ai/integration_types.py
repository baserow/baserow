from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.utils import validate_data
from baserow.api.workspaces.serializers import get_generative_ai_settings_serializer
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application


class AIIntegrationType(IntegrationType):
    """
    Integration type for connecting to generative AI providers. Allows users to either
    inherit workspace-level AI settings (default) or override them per integration.
    Explicit overrides are returned here. Otherwise, the database provider resolver
    owns workspace inheritance, including legacy workspace JSON compatibility.
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
            "present, workspace settings are inherited. A complete connection uses "
            "its own credentials and explicit model list; omitting models inherits "
            "available models, while an empty list disables them. An incomplete "
            "connection can only restrict inherited model availability. Structure: "
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

        Database-only providers are valid here because complete overrides are passed
        atomically to the runtime instead of being stored in legacy workspace settings.

        :param values: The integration values supplied by the caller.
        :param user: The user creating or updating the integration.
        :returns: The normalized values prepared by the base integration type.
        :raises RequestBodyValidationException: If provider settings fail their
            registered serializer's validation.
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

    def get_integration_provider_settings(
        self, integration: AIIntegration, provider_type: str
    ) -> dict[str, Any] | None:
        """
        Return the integration-level settings override for a provider.

        :param integration: The AI integration to read the override from.
        :param provider_type: The generative AI provider type key.
        :returns: The stored override, including an explicit empty dictionary, or
            None when no dictionary is stored for this provider. This does not
            validate whether the override defines a complete connection.
        """

        provider_settings = integration.ai_settings.get(provider_type)
        if isinstance(provider_settings, dict):
            return provider_settings
        return None

    def get_provider_settings(
        self, integration: AIIntegration, provider_type: str
    ) -> Dict[str, Any]:
        """
        Get explicit settings for a provider, or defer to workspace resolution.

        An empty result tells the generative AI model type to resolve the live
        workspace provider and its compatibility fallbacks itself.

        :param integration: The AI integration whose provider settings are requested.
        :param provider_type: The generative AI provider type.
        :returns: Explicit provider settings, or an empty dictionary when
            workspace inheritance should be used.
        """

        provider_settings = self.get_integration_provider_settings(
            integration, provider_type
        )
        if provider_settings is not None:
            return provider_settings

        return {}

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
