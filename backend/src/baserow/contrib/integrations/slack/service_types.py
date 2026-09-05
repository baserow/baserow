from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils.translation import gettext as _

from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.integrations.slack.integration_types import SlackBotIntegrationType
from baserow.contrib.integrations.slack.models import SlackWriteMessageService
from baserow.contrib.integrations.utils import (
    get_http_request_function,
    read_response_within_limit,
)
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    RemoteRefusedDispatchException,
    ResponseTooLargeDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict

SLACK_REQUEST_TIMEOUT_SECONDS = 10

# The timeout is per socket operation: connect, headers, body.
SLACK_REQUEST_SOCKET_OPERATIONS = 3


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
                # Refused here rather than by the insert, which answers 500.
                max_length=SlackWriteMessageService._meta.get_field(
                    "channel"
                ).max_length,
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
        :raises RemoteRefusedDispatchException: If Slack refused the message.
        """

        try:
            token = service.integration.specific.token
            response = get_http_request_function()(
                method="POST",
                url=f"{settings.INTEGRATIONS_SLACK_API_URL}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "channel": f"#{service.channel}",
                    "text": resolved_values["text"],
                },
                timeout=SLACK_REQUEST_TIMEOUT_SECONDS,
                # Each hop would get a fresh timeout, outliving the row lock.
                allow_redirects=False,
                # Read in chunks below, under a size and a time limit.
                stream=True,
            )
            read_response_within_limit(response, SLACK_REQUEST_TIMEOUT_SECONDS)
        except ResponseTooLargeDispatchException:
            # Names no address, so it travels as it is.
            raise
        except UnacceptableAddressException as e:
            # Nothing was sent, so this click is not charged for it.
            raise AddressNotAllowedDispatchException(
                f"Invalid URL: {settings.INTEGRATIONS_SLACK_API_URL}"
            ) from e
        except request_exceptions.RequestException as e:
            # Not `str(e)`: requests names the whole URL, and this one's query
            # string carries the channel and the resolved message. This also
            # catches requests' own ConnectionError, which is not the builtin.
            raise UnexpectedDispatchException(
                f"The request to {settings.INTEGRATIONS_SLACK_API_URL} failed: "
                f"{type(e).__name__}."
            ) from e
        except Exception as e:
            # Not `logger.exception`: loguru prints the frame locals, and this
            # frame holds the bot token.
            logger.error(
                "Error while dispatching the Slack message: {exception}.",
                exception=type(e).__name__,
            )
            raise UnexpectedDispatchException(
                f"Unknown error: {type(e).__name__}"
            ) from e

        try:
            response_data = response.json()
        except ValueError as e:
            # The endpoint is configurable, so the answer can be a proxy's
            # HTML or a redirect body rather than anything Slack sends.
            raise RemoteRefusedDispatchException(
                "The answer was not in the shape Slack replies with."
            ) from e

        # Valid JSON, but not an object at all.
        if not isinstance(response_data, dict):
            raise RemoteRefusedDispatchException(
                "The answer was not in the shape Slack replies with."
            )

        if not response_data.get("ok", False):
            # The common codes. Full list:
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
            error_code = response_data.get("error")
            # Anything but a string cannot key the table, and must not be
            # repeated into the message either.
            if not isinstance(error_code, str):
                error_code = "unknown"
            misconfigured_service_message = misconfigured_service_error_codes.get(
                error_code, misconfigured_service_error_codes["default"]
            ).format(channel=service.channel, error_code=error_code)
            # The post was made, so the click is charged for it.
            raise RemoteRefusedDispatchException(misconfigured_service_message)
        return {"data": response_data}

    def dispatch_transform(self, data):
        # Left wrapped, and `generate_schema` describes the wrapper, so the
        # path the data explorer offers resolves against what a dispatch
        # stores. Unwrapping instead would mean migrating every sample an
        # earlier version wrote.
        return DispatchResult(data=data)

    def max_dispatch_seconds(self, service: SlackWriteMessageService) -> int:
        return SLACK_REQUEST_TIMEOUT_SECONDS * SLACK_REQUEST_SOCKET_OPERATIONS

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).select_related("integration")

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

        # `ts` is the message reference, for threading and updating. Under
        # `data`, because that is where the dispatch puts them.
        answer = {
            "ok": {"type": "boolean", "title": _("OK")},
            "channel": {"type": "string", "title": _("Channel")},
            "ts": {"type": "string", "title": _("Message timestamp")},
        }
        # Names what the caller wants out of the answer, so it applies inside
        # the wrapper rather than to it.
        properties = {
            name: prop
            for name, prop in answer.items()
            if allowed_fields is None or name in allowed_fields
        }
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "title": _("Data"),
                    "properties": properties,
                }
            },
        }
