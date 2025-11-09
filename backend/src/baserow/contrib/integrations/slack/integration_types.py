from typing import Any, Dict

from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application


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

    def import_serialized(
        self,
        application: Application,
        serialized_values: Dict[str, Any],
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
    ) -> SlackBotIntegration:
        """
        Imports a serialized integration. Ensures that if we're importing an exported
        integration (where `token` will be `None`), we set it to an empty string.
        """

        if serialized_values["token"] is None:
            serialized_values["token"] = ""  # nosec B105

        return super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
