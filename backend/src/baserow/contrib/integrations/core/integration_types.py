from typing import Any, Dict

from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict


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
    sensitive_fields = ["host", "port", "use_tls", "username", "password"]
    secret_fields = ["password"]
    # Changing where the request goes, or downgrading it to plaintext, would
    # send the stored password somewhere its owner never agreed to.
    secret_field_dependencies = {"password": ["host", "port", "use_tls"]}

    request_serializer_field_names = ["host", "port", "use_tls", "username", "password"]
    request_serializer_field_overrides = {}
    serializer_field_extra_kwargs = {
        "password": {
            "help_text": "The SMTP password. Write-only: it is never returned, "
            "see `has_password`. Omit it to keep the stored password; send an "
            "empty string or null to clear it."
        }
    }

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        **kwargs,
    ) -> Any:
        if prop_name == "host":
            return value if value is not None else ""
        if prop_name == "port":
            return value if value is not None else 587
        if prop_name == "use_tls":
            return value if value is not None else True
        return super().deserialize_property(prop_name, value, id_mapping, **kwargs)
