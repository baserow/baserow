from typing import Any

from baserow.contrib.integrations.core.inbound_email import (
    is_inbound_email_configured,
)
from baserow.contrib.integrations.core.models import CoreHTTPTriggerService
from baserow.core.services.models import Service

from .data_providers import rows_as_text, trigger_data_as_text
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


class InboundEmailAgentTriggerType(AgentTriggerType):
    type = "email_trigger"

    def is_offered(self) -> bool:
        return is_inbound_email_configured()

    def get_event_text(
        self, service: Service, event_payload: dict[str, Any]
    ) -> str | None:
        """
        :param service: The inbound email trigger service that received the email.
        :param event_payload: The email as the receiver normalized it.
        :return: Who sent the email, its subject and its text. What the mail
            servers added stays out, as an Agent has no use for it.
        """

        return trigger_data_as_text(
            {
                "from": event_payload.get("from"),
                "subject": event_payload.get("subject"),
                "body": event_payload.get("body_text"),
            }
        )


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
        return trigger_data_as_text(values) + rows_as_text(service, event_payload)
