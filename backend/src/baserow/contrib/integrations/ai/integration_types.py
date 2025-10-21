from rest_framework import serializers

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict

from .models import LMIntegration


class LMIntegrationType(IntegrationType):
    type = "lm"
    model_class = LMIntegration

    class SerializedDict(IntegrationDict):
        api_key: str
        model: str
        api_base_url: str | None

    serializer_field_names = ["api_key", "model", "api_base_url"]
    allowed_fields = ["api_key", "model", "api_base_url"]
    sensitive_fields = ["api_key"]

    request_serializer_field_names = ["api_key", "model", "api_base_url"]
    request_serializer_field_overrides = {
        "api_base_url": serializers.CharField(
            help_text=LMIntegration._meta.get_field("api_base_url").help_text,
            required=False,
            allow_null=True,
            allow_blank=True,
        ),
    }
