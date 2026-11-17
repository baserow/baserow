from typing import Any

from baserow.contrib.integrations.core.models import CoreHTTPTriggerService

from .registries import AgentTriggerType


class HTTPAgentTriggerType(AgentTriggerType):
    type = "http_trigger"
    # A link preview or a mail scanner opening the URL must not start a run.
    default_service_values = {"exclude_get": True}
    # A firing starts a run in the background, so no caller waits for a response.
    unused_service_fields = ("wait_for_response", "response_timeout_seconds")

    def get_event_text(
        self, service: CoreHTTPTriggerService, event_payload: dict[str, Any]
    ) -> str | None:
        """
        :param service: The HTTP trigger service that received the request.
        :param event_payload: The request as the webhook view parsed it.
        :return: The request body as it was sent, or None when it had none. The
            headers and the sender's address can hold secrets, so they stay out.
        """

        return event_payload.get("raw_body") or None
