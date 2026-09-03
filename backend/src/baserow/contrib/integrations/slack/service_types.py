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
                # The column holds 80, so a longer one is refused here rather
                # than by the insert, which would answer 500.
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
        :raises ServiceImproperlyConfiguredDispatchException: If the Slack service is
            improperly configured, indicated by specific error codes from the Slack API.
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
                # `read_response_within_limit` pulls the body in, in chunks,
                # so a slow or oversized answer cannot outlive the lock this
                # service's `max_dispatch_seconds` sizes.
                stream=True,
            )
            read_response_within_limit(response, SLACK_REQUEST_TIMEOUT_SECONDS)
            response_data = response.json()
        except ResponseTooLargeDispatchException:
            # Too big. The message names no address, so it travels as it is
            # rather than as an unknown error.
            raise
        except UnacceptableAddressException as e:
            # Refused before anything was sent, so a caller counting outbound
            # traffic must not count it. The HTTP service answers the same.
            raise AddressNotAllowedDispatchException(
                f"Invalid URL: {settings.INTEGRATIONS_SLACK_API_URL}"
            ) from e
        except ConnectionError as e:
            raise UnexpectedDispatchException(
                f"Invalid URL: {settings.INTEGRATIONS_SLACK_API_URL}"
            ) from e
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(str(e)) from e
        except Exception as e:
            # Not `logger.exception`: loguru prints the frame locals beside
            # the traceback, and this frame holds the bot token. Only the
            # class of the failure is logged.
            logger.error(
                "Error while dispatching the Slack message: {exception}. The "
                "failure itself is not logged: it names the credential the "
                "request carried.",
                exception=type(e).__name__,
            )
            raise UnexpectedDispatchException(f"Unknown error: {str(e)}") from e

        # The endpoint is configurable, so a proxy or a gateway can answer
        # with valid JSON that is not an object at all. Read as a refusal
        # rather than indexed into.
        if not isinstance(response_data, dict):
            raise RemoteRefusedDispatchException(
                "The message was not accepted, and the answer was not in the "
                "shape Slack replies with."
            )

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
            error_code = response_data.get("error")
            # Slack answers with a string. Anything else cannot key the table
            # below, and must not be repeated into the message either.
            if not isinstance(error_code, str):
                error_code = "unknown"
            misconfigured_service_message = misconfigured_service_error_codes.get(
                error_code, misconfigured_service_error_codes["default"]
            ).format(channel=service.channel, error_code=error_code)
            # The post was already made, so a caller counting outbound
            # traffic charges the click for it.
            raise RemoteRefusedDispatchException(misconfigured_service_message)
        return {"data": response_data}

    def dispatch_transform(self, data):
        # Unwrapped like the HTTP and email services, so the answer sits where
        # `generate_schema` says a later step can read it.
        return DispatchResult(data=data["data"])

    def max_dispatch_seconds(self, service: SlackWriteMessageService) -> int:
        return SLACK_REQUEST_TIMEOUT_SECONDS

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

        # What `chat.postMessage` answers with that a later step can use:
        # `ts` is the message reference for threading and updating.
        all_properties = {
            "ok": {"type": "boolean", "title": _("OK")},
            "channel": {"type": "string", "title": _("Channel")},
            "ts": {"type": "string", "title": _("Message timestamp")},
        }
        properties = {
            name: prop
            for name, prop in all_properties.items()
            if allowed_fields is None or name in allowed_fields
        }
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }
