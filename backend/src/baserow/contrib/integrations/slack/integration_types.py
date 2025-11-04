from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict


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
