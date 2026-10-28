from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.api.utils import validate_data
from baserow.api.workspaces.serializers import get_generative_ai_settings_serializer
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.integrations.registries import (
    IntegrationType,
    check_secret_targets_unchanged,
)
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application

AI_SETTINGS_SECRET = "api_key"
# Settings that only shape requests to the provider.
AI_SETTINGS_NON_TARGETS = {AI_SETTINGS_SECRET, "models"}


class AISettingsResponseField(serializers.JSONField):
    """
    Returns the provider settings with each write-only `api_key` replaced by a
    `has_api_key` boolean.
    """

    def to_representation(self, value):
        return {
            provider: (
                {
                    **{k: v for k, v in settings.items() if k != AI_SETTINGS_SECRET},
                    f"has_{AI_SETTINGS_SECRET}": bool(settings.get(AI_SETTINGS_SECRET)),
                }
                if isinstance(settings, dict)
                else settings
            )
            for provider, settings in (value or {}).items()
        }


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
        "ai_settings": AISettingsResponseField(
            required=False,
            default=dict,
            help_text="Per-provider AI settings overrides. If a provider key is not "
            "present, workspace settings are inherited. A complete connection uses "
            "its own credentials and explicit model list; omitting models inherits "
            "available models, while an empty list disables them. An incomplete "
            "connection can only restrict inherited model availability. The "
            "`api_key` is write-only and is returned as `has_api_key`. Structure: "
            '{"openai": {"has_api_key": true, "models": [...], "organization": ""}, '
            "...}",
        ),
    }

    request_serializer_field_names = ["ai_settings"]
    request_serializer_field_overrides = {
        "ai_settings": serializers.JSONField(
            required=False,
            default=dict,
            help_text="Per-provider AI settings overrides. On update, omit a "
            "provider's `api_key` to keep the stored one; it must be supplied "
            "again when any other connection setting of that provider changes.",
        ),
    }

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        application: Application | None = None,
        instance: AIIntegration | None = None,
    ) -> Dict[str, Any]:
        """Validate explicit per-integration provider settings before saving.

        :param values: The integration values supplied by the caller.
        :param user: The user creating or updating the integration.
        :returns: The normalized values prepared by the base integration type.
        :raises RequestBodyValidationException: If provider settings fail their
            registered serializer's validation.
        :raises IntegrationCredentialRequired: If a provider's connection settings
            change on update without its stored `api_key` being supplied again.
        """

        if "ai_settings" not in values:
            if instance is None:
                values["ai_settings"] = {}
            return super().prepare_values(
                values, user, application=application, instance=instance
            )

        if values["ai_settings"]:
            validated_settings = validate_data(
                get_generative_ai_settings_serializer(),
                values["ai_settings"],
                return_validated=True,
            )
            values["ai_settings"] = validated_settings

        if instance is not None:
            self._keep_stored_api_keys(instance, values["ai_settings"])

        return super().prepare_values(
            values, user, application=application, instance=instance
        )

    def _keep_stored_api_keys(
        self, instance: AIIntegration, ai_settings: Dict[str, Any]
    ) -> None:
        """
        Copies the stored `api_key` into each provider whose new settings omit it,
        because the API never returns it for the caller to send back.

        Every provider setting other than the key and `models` is a target that
        may choose where the key is sent, as in `secret_field_dependencies`.

        :raises IntegrationCredentialRequired: If a target of that provider
            changed.
        """

        for provider_type, provider_settings in ai_settings.items():
            stored_settings = instance.ai_settings.get(provider_type)
            if (
                AI_SETTINGS_SECRET in provider_settings
                or not isinstance(stored_settings, dict)
                or not stored_settings.get(AI_SETTINGS_SECRET)
            ):
                continue

            settings_serializer = generative_ai_model_type_registry.get(
                provider_type
            ).get_settings_serializer()
            targets = [
                name
                for name in settings_serializer().fields
                if name not in AI_SETTINGS_NON_TARGETS
            ]
            # A blank setting is stored as either "" or nothing at all.
            check_secret_targets_unchanged(
                f"{provider_type}.{AI_SETTINGS_SECRET}",
                targets,
                provider_settings,
                lambda target: stored_settings.get(target, ""),
            )

            provider_settings[AI_SETTINGS_SECRET] = stored_settings[AI_SETTINGS_SECRET]

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
        import_export_config=None,
    ) -> AIIntegration:
        if cache is None:
            cache = {}

        # AI settings are sensitive data, the serialized data will set it `None`.
        serialized_values["ai_settings"] = serialized_values["ai_settings"] or {}

        return super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
