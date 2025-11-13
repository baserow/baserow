from typing import Any, Dict, List, Optional

from django.utils.translation import gettext as _

from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from baserow.contrib.integrations.slack.integration_types import SlackBotIntegrationType
from baserow.contrib.integrations.slack.models import SlackWriteMessageService
from baserow.contrib.integrations.utils import get_http_request_function
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict


class SlackWriteMessageServiceType(ServiceType):
    type = "slack_write_message"
    model_class = SlackWriteMessageService
    dispatch_types = [DispatchTypes.ACTION]
    integration_type = SlackBotIntegrationType.type

    allowed_fields = ["integration_id", "channel", "text"]
    serializer_field_names = ["integration_id", "channel", "text"]
    public_serializer_field_names = ["integration_id", "channel", "text"]
    simple_formula_fields = ["text"]

    class SerializedDict(ServiceDict):
        channel: str
        text: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the Slack bot integration.",
            ),
            "channel": serializers.CharField(
                help_text=SlackWriteMessageService._meta.get_field("channel").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "text": FormulaSerializerField(
                help_text=SlackWriteMessageService._meta.get_field("text").help_text
            ),
        }

    @property
    def public_serializer_field_overrides(self):
        # When we're exposing this service type via a "public" serializer,
        #  use the same overrides as usual.
        return self.serializer_field_overrides

    def formulas_to_resolve(
        self, service: SlackWriteMessageService
    ) -> list[FormulaToResolve]:
        return [
            FormulaToResolve(
                "text",
                service.text,
                ensure_string,
                'property "text"',
            ),
        ]

    def dispatch_data(
        self,
        service: SlackWriteMessageService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Dispatches the Slack write message service by sending a message to the
        specified Slack channel using the Slack API.

        :param service: The SlackWriteMessageService instance to be dispatched.
        :param resolved_values: A dictionary containing the resolved values for the
            service's fields, including the message text.
        :param dispatch_context: The context in which the dispatch is occurring.
        :return: A dictionary containing the response data from the Slack API.
        :raises UnexpectedDispatchException: If there's an error after the HTTP request.
        :raises ServiceImproperlyConfiguredDispatchException: If the Slack service is
            improperly configured, indicated by specific error codes from the Slack API.
        """

        try:
            token = service.integration.specific.token
            response = get_http_request_function()(
                method="POST",
                url="https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "channel": f"#{service.channel}",
                    "text": resolved_values["text"],
                },
                timeout=10,
            )
            response_data = response.json()
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(str(e)) from e
        except Exception as e:
            logger.exception("Error while dispatching HTTP request")
            raise UnexpectedDispatchException(f"Unknown error: {str(e)}") from e

        # If we've found that the response indicates an error, we raise a
        # ServiceImproperlyConfiguredDispatchException with a relevant message.
        if not response_data.get("ok", False):
            # Some frequently occurring error codes from Slack API. Full list:
            # https://docs.slack.dev/reference/methods/chat.postMessage/
            misconfigured_service_error_codes = {
                "no_text": "The message text is missing.",
                "invalid_auth": "Invalid bot user token.",
                "channel_not_found": "The channel #{channel} was not found.",
                "not_in_channel": "Your app has not been invited to channel #{channel}.",
                "rate_limited": "Your app has sent too many requests in a "
                "short period of time.",
                "default": "An unknown error occurred while sending the message, "
                "the error code was: {error_code}",
            }
            error_code = response_data["error"]
            misconfigured_service_message = misconfigured_service_error_codes.get(
                error_code, misconfigured_service_error_codes["default"]
            ).format(channel=service.channel, error_code=error_code)
            raise ServiceImproperlyConfiguredDispatchException(
                misconfigured_service_message
            )
        return {"data": response_data}

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def get_schema_name(self, service: SlackWriteMessageService) -> str:
        return f"SlackWriteMessage{service.id}Schema"

    def generate_schema(
        self,
        service: SlackWriteMessageService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates a JSON schema for the Slack write message service.

        :param service: The SlackWriteMessageService instance for which to generate the
            schema.
        :param allowed_fields: An optional list of fields to include in the schema.
        :return: A dictionary representing the JSON schema of the service.
        """

        properties = {}
        if allowed_fields is None or "ok" in allowed_fields:
            properties.update(
                **{
                    "ok": {
                        "type": "boolean",
                        "title": _("OK"),
                    },
                }
            )
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }
