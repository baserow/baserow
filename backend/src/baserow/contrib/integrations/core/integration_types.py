from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from rest_framework.exceptions import ValidationError

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
        use_ssl: bool
        username: str
        password: str

    serializer_field_names = [
        "host",
        "port",
        "use_tls",
        "use_ssl",
        "username",
        "password",
    ]
    allowed_fields = ["host", "port", "use_tls", "use_ssl", "username", "password"]
    sensitive_fields = ["host", "port", "use_tls", "use_ssl", "username", "password"]
    secret_fields = ["password"]
    # Changing where the request goes, or downgrading it to plaintext, would
    # send the stored password somewhere its owner never agreed to.
    secret_field_dependencies = {"password": ["host", "port", "use_tls", "use_ssl"]}

    request_serializer_field_names = [
        "host",
        "port",
        "use_tls",
        "use_ssl",
        "username",
        "password",
    ]
    request_serializer_field_overrides = {}
    serializer_field_extra_kwargs = {
        "password": {
            "help_text": "The SMTP password. Write-only: it is never returned, "
            "see `has_password`. Omit it to keep the stored password; send an "
            "empty string or null to clear it."
        }
    }

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        """
        STARTTLS and implicit SSL/TLS are two ways of encrypting the same
        connection, so only one can be on. Turning one on turns the other off,
        which keeps a partial update from leaving both enabled.
        """

        if values.get("use_tls") and values.get("use_ssl"):
            raise ValidationError(
                {"use_ssl": "`use_tls` and `use_ssl` can't both be enabled."},
                code="invalid",
            )
        if values.get("use_ssl"):
            values["use_tls"] = False
        elif values.get("use_tls"):
            values["use_ssl"] = False

        return super().prepare_values(values, user)

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
        if prop_name == "use_ssl":
            return value if value is not None else False
        return super().deserialize_property(prop_name, value, id_mapping, **kwargs)
