from typing import Any, Dict, List, Optional

from django.utils.translation import gettext as _

from advocate import UnacceptableAddressException
from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from baserow.contrib.integrations.core.service_types import CoreServiceType
from baserow.contrib.integrations.slack.integration_types import SlackBotIntegrationType
from baserow.contrib.integrations.slack.models import SlackWriteMessageService
from baserow.contrib.integrations.utils import get_http_request_function
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import UnexpectedDispatchException
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict


class SlackWriteMessageServiceType(CoreServiceType):
    type = "slack_write_message"
    model_class = SlackWriteMessageService
    dispatch_types = [DispatchTypes.ACTION]
    integration_type = SlackBotIntegrationType.type

    allowed_fields = ["integration_id", "channel", "text"]
    serializer_field_names = ["integration_id", "channel", "text"]
    simple_formula_fields = ["text"]

    class SerializedDict(ServiceDict):
        channel: str
        text: str

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
        """ """

        url = "https://slack.com/api/chat.postMessage"
        try:
            token = service.integration.specific.token
            response = get_http_request_function()(
                method="POST",
                url=url,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "channel": f"#{service.channel}",
                    "text": resolved_values["text"],
                },
                timeout=10,
            )
            print(response.json())

            return {"data": response.json()}

        except (UnacceptableAddressException, ConnectionError) as e:
            raise UnexpectedDispatchException(f"Invalid URL: {url}") from e
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(str(e)) from e
        except Exception as e:
            logger.exception("Error while dispatching HTTP request")
            raise UnexpectedDispatchException(f"Unknown error: {str(e)}") from e

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def get_schema_name(self, service: SlackWriteMessageService) -> str:
        return f"SlackWriteMessage{service.id}Schema"

    def generate_schema(
        self,
        service: SlackWriteMessageService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                "ok": {
                    "type": "boolean",
                    "title": _("OK"),
                },
            },
        }
