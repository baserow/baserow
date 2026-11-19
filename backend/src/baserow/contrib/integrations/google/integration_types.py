from django.conf import settings
from django.urls import include, path

from rest_framework import serializers

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict

from .models import GoogleIntegration


class GoogleIntegrationType(IntegrationType):
    class SerializedDict(IntegrationDict):
        client_mode: str
        client_id: str
        client_secret: str

    type = "google"
    model_class = GoogleIntegration
    allowed_fields = ["client_mode", "client_id", "client_secret"]
    serializer_field_names = [
        *allowed_fields,
        "connected",
        "account_email",
        "granted_scopes",
        "context_data",
    ]
    request_serializer_field_names = allowed_fields
    request_serializer_field_overrides = {}
    serializer_field_overrides = {
        "connected": serializers.BooleanField(read_only=True, source="is_connected"),
        "context_data": serializers.ReadOnlyField(),
        "account_email": serializers.EmailField(read_only=True),
        "granted_scopes": serializers.ListField(
            child=serializers.CharField(), read_only=True
        ),
    }
    sensitive_fields = ["client_secret", "account_email", "granted_scopes", "connected"]
    secret_fields = ["client_secret"]
    secret_field_dependencies = {"client_secret": ["client_id", "client_mode"]}

    def get_api_urls(self):
        from .api import urls

        return [path("integrations/google/", include((urls, "google")))]

    def get_context_data(self, instance):
        """Expose client availability and the callback URL without global credentials."""
        from .oauth import redirect_uri

        return {
            "redirect_uri": redirect_uri(),
            "default_client_available": bool(
                settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
            ),
        }

    def get_dropped_secrets(self, values, instance):
        if values.get("client_mode") == "default":
            return {"client_secret"}
        return set()

    def prepare_values(self, values, user, application=None, instance=None):
        """Invalidate credentials and pending sign-ins when the OAuth client changes."""
        values = super().prepare_values(values, user, application, instance)
        if values.get("client_mode") == "default":
            values["client_secret"] = ""
        if instance and any(
            key in values and values[key] != getattr(instance, key)
            for key in self.allowed_fields
        ):
            instance.clear_tokens()
            instance.generation += 1
            instance.save()
        return values

    def serialize_property(self, integration, prop_name, **kwargs):
        if prop_name == "client_secret":
            return ""
        return super().serialize_property(integration, prop_name, **kwargs)

    def import_serialized(self, parent, serialized_values, id_mapping, **kwargs):
        """Imports and duplicates always require a new Google authorization."""
        values = dict(serialized_values)
        for key in (
            "connected",
            "account_email",
            "granted_scopes",
            "client_secret",
            "context_data",
        ):
            values.pop(key, None)
        integration = super().import_serialized(parent, values, id_mapping, **kwargs)
        config = kwargs.get("import_export_config")
        if config and config.is_publishing:
            source = GoogleIntegration.objects.get(
                pk=serialized_values["id"],
                application__workspace_id=parent.workspace_id,
            )
            integration.credential_source = source.credential_source or source
            integration.save(update_fields=["credential_source"])
        return integration
