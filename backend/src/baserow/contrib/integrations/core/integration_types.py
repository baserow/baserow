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

    request_serializer_field_names = ["host", "port", "use_tls", "username", "password"]
    request_serializer_field_overrides = {}

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
