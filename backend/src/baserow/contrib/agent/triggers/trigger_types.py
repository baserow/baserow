import json
from typing import Any

from baserow.contrib.integrations.core.models import CoreHTTPTriggerService
from baserow.core.services.models import Service

from .data_providers import rows_as_text
from .registries import AgentTriggerType

ROWS_TRIGGER_TYPES = (
    "local_baserow_rows_created",
    "local_baserow_rows_updated",
    "local_baserow_rows_deleted",
)


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


class RowsAgentTriggerType(AgentTriggerType):
    """Hosts a trigger type whose events are the rows that changed in a table."""

    def get_event_text(
        self, service: Service, event_payload: dict[str, Any]
    ) -> str | None:
        """
        :param service: The specific trigger service the event fired.
        :param event_payload: The event's rows, or one batch of them.
        :return: The event's values as fenced JSON, then its rows as
            `trigger.rows` reads them.
        """

        values = service.get_type().get_event_context(service, event_payload)
        return (
            f"Trigger data:\n```json\n{json.dumps(values, default=str, indent=2)}"
            f"\n```{rows_as_text(service, event_payload)}"
        )
