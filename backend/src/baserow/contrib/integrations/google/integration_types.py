from baserow.contrib.integrations.oauth_account.integration_types import (
    OAuthAccountIntegrationDict,
    OAuthAccountIntegrationTypeMixin,
)
from baserow.core.integrations.registries import IntegrationType

from .models import GoogleIntegration
from .providers import GoogleOAuthProvider


class GoogleIntegrationType(OAuthAccountIntegrationTypeMixin, IntegrationType):
    type = "google"
    model_class = GoogleIntegration
    provider = GoogleOAuthProvider()

    class SerializedDict(OAuthAccountIntegrationDict):
        client_mode: str
        client_id: str
        client_secret: str
        connected_client: str

    allowed_fields = ["client_mode", "client_id", "client_secret"]
    serializer_field_names = [
        *OAuthAccountIntegrationTypeMixin.serializer_field_names,
        *allowed_fields,
    ]
    request_serializer_field_names = allowed_fields
    secret_field_dependencies = {"client_secret": ["client_id", "client_mode"]}

    @property
    def sensitive_fields(self):
        return [*super().sensitive_fields, "client_secret"]

    @property
    def secret_fields(self):
        return [*super().secret_fields, "client_secret"]

    def get_dropped_secrets(self, values, instance):
        return {"client_secret"} if values.get("client_mode") == "default" else set()

    def prepare_values(self, values, user, application=None, instance=None):
        """A different Google client requires a fresh connection through the shared flow."""
        values = super().prepare_values(values, user, application, instance)
        if values.get("client_mode") == "default":
            values["client_secret"] = ""
        if instance and any(
            key in values and values[key] != getattr(instance, key)
            for key in self.allowed_fields
        ):
            fields = instance.clear_tokens()
            instance.generation += 1
            instance.save(update_fields=[*fields, "generation"])
        return values

    def deserialize_property(self, prop_name, value, id_mapping, **kwargs):
        """Use the model default for a client secret redacted from an export."""
        if prop_name == "client_secret" and value is None:
            return self.model_class._meta.get_field(prop_name).get_default()
        return super().deserialize_property(prop_name, value, id_mapping, **kwargs)
