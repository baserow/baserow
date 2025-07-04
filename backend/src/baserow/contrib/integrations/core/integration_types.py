from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict

from .models import SMTPIntegration


class SMTPIntegrationType(IntegrationType):
    type = "smtp"
    model_class = SMTPIntegration

    class SerializedDict(IntegrationDict):
        host: str
        port: int
        use_tls: bool
        username: str
        password: str

    serializer_field_names = ["host", "port", "use_tls", "username", "password"]
    allowed_fields = ["host", "port", "use_tls", "username", "password"]
    sensitive_fields = ["password"]

    request_serializer_field_names = ["host", "port", "use_tls", "username", "password"]
    request_serializer_field_overrides = {}

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        return super().prepare_values(values, user)

    def enhance_queryset(self, queryset):
        return queryset
