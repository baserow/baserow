from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict

from baserow.contrib.integrations.core.models import (
    SMTPIntegration,
    SlackBotIntegration,
)


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
    sensitive_fields = ["username", "password"]

    request_serializer_field_names = ["host", "port", "use_tls", "username", "password"]
    request_serializer_field_overrides = {}


class SlackBotIntegrationType(IntegrationType):
    type = "slack_bot"
    model_class = SlackBotIntegration

    class SerializedDict(IntegrationDict):
        token: str

    serializer_field_names = ["token"]
    allowed_fields = ["token"]
    sensitive_fields = ["token"]

    request_serializer_field_names = ["token"]
    request_serializer_field_overrides = {}
