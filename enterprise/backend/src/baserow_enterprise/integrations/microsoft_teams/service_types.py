import html
import time
from typing import Any, Dict, List, Optional

from django.utils.translation import gettext as _

from rest_framework import serializers

from baserow.contrib.integrations.microsoft.service_types import (
    MicrosoftServiceTypeMixin,
)
from baserow.contrib.integrations.oauth_account.exceptions import ProviderAPIError
from baserow.contrib.integrations.oauth_account.service_types import (
    API_OPERATION_TIMEOUT_SECONDS,
    BUSY_STATUS_CODES,
)
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict
from baserow_enterprise.features import MICROSOFT_TEAMS
from baserow_enterprise.integrations.microsoft_teams.models import (
    MicrosoftTeamsDestinationType,
    MicrosoftTeamsWriteMessageService,
)
from baserow_premium.license.handler import LicenseHandler

PERSONAL_ACCOUNT_MESSAGE = (
    "Teams messages can only be sent from a work or school Microsoft account. "
    "Connect one in the integration settings."
)

# The ids each destination type sends to, in the order of the Graph path.
DESTINATION_ID_FIELDS = {
    MicrosoftTeamsDestinationType.CHANNEL: ["team_id", "channel_id"],
    MicrosoftTeamsDestinationType.CHAT: ["chat_id"],
}


def message_to_html(text: str) -> str:
    """
    The Teams HTML of a plain text message. The text is escaped, so row data
    can't add markup, and its line breaks become `<br>`, which a `text` body
    would lose.

    :param text: The resolved message.
    :return: The HTML to send.
    """

    escaped = html.escape(text)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


class MicrosoftTeamsServiceTypeMixin(MicrosoftServiceTypeMixin):
    """The Microsoft permissions, license and messages of the Teams services."""

    required_scopes = [
        "ChannelMessage.Send",
        "ChatMessage.Send",
        # For picking the team, channel or chat, see `MicrosoftTeamsHandler`.
        # `Chat.ReadBasic` also lists the members of a chat, which names 1:1
        # chats.
        "Team.ReadBasic.All",
        "Channel.ReadBasic.All",
        "Chat.ReadBasic",
    ]
    permission_description = "send Teams messages"

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(MICROSOFT_TEAMS, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            MICROSOFT_TEAMS, workspace
        )

    def api_error_exception(self, exc: ProviderAPIError) -> Exception:
        if exc.status_code in BUSY_STATUS_CODES:
            return RemoteBusyDispatchException(
                "Microsoft Teams asked for this message to be sent again later."
            )
        if exc.status_code == 403:
            return RemoteRefusedDispatchException(
                "The connected Microsoft account can't post in this channel or "
                "chat. It must be a member, have a Teams license, and be allowed "
                "to post there."
            )
        if exc.status_code == 404:
            return RemoteRefusedDispatchException(
                "The team, channel or chat wasn't found."
            )
        return super().api_error_exception(exc)


class MicrosoftTeamsWriteMessageServiceType(
    MicrosoftTeamsServiceTypeMixin, ServiceType
):
    type = "microsoft_teams_write_message"
    model_class = MicrosoftTeamsWriteMessageService
    dispatch_types = [DispatchTypes.ACTION]
    is_external = True

    allowed_fields = [
        "integration_id",
        "destination_type",
        "team_id",
        "channel_id",
        "chat_id",
        "destination_label",
        "message",
    ]
    serializer_field_names = allowed_fields
    simple_formula_fields = ["team_id", "channel_id", "chat_id", "message"]

    class SerializedDict(ServiceDict):
        destination_type: str
        team_id: BaserowFormulaObject
        channel_id: BaserowFormulaObject
        chat_id: BaserowFormulaObject
        destination_label: str
        message: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        def help_text(name):
            return MicrosoftTeamsWriteMessageService._meta.get_field(name).help_text

        return {
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the Microsoft integration.",
            ),
            "destination_type": serializers.ChoiceField(
                choices=MicrosoftTeamsDestinationType.choices,
                required=False,
                help_text=help_text("destination_type"),
            ),
            "team_id": FormulaSerializerField(
                required=False, help_text=help_text("team_id")
            ),
            "channel_id": FormulaSerializerField(
                required=False, help_text=help_text("channel_id")
            ),
            "chat_id": FormulaSerializerField(
                required=False, help_text=help_text("chat_id")
            ),
            "destination_label": serializers.CharField(
                required=False,
                allow_blank=True,
                max_length=MicrosoftTeamsWriteMessageService._meta.get_field(
                    "destination_label"
                ).max_length,
                help_text=help_text("destination_label"),
            ),
            "message": FormulaSerializerField(
                required=False, help_text=help_text("message")
            ),
        }

    def get_configuration_errors(
        self, service: MicrosoftTeamsWriteMessageService
    ) -> dict[str, str]:
        errors = {}
        required = [
            *DESTINATION_ID_FIELDS.get(service.destination_type, []),
            "message",
        ]
        for field in required:
            if not (getattr(service, field) or {}).get("formula", "").strip():
                errors[field] = "required"
        return errors

    def formulas_to_resolve(
        self, service: MicrosoftTeamsWriteMessageService
    ) -> list[FormulaToResolve]:
        return [
            *[
                FormulaToResolve(
                    field, getattr(service, field), ensure_string, f'property "{field}"'
                )
                for field in DESTINATION_ID_FIELDS.get(service.destination_type, [])
            ],
            FormulaToResolve(
                "message", service.message, ensure_string, 'property "message"'
            ),
        ]

    def dispatch(
        self,
        service: MicrosoftTeamsWriteMessageService,
        dispatch_context: DispatchContext,
    ) -> DispatchResult:
        self.raise_if_deactivated(dispatch_context.workspace)
        return super().dispatch(service, dispatch_context)

    def dispatch_data(
        self,
        service: MicrosoftTeamsWriteMessageService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Posts the message to the channel or chat, as the integration's account.

        :raises ServiceImproperlyConfiguredDispatchException: When the action
            misses a destination or a message, or its account can't be used.
        :raises RemoteRefusedDispatchException: When Teams refused the message.
        :raises RemoteBusyDispatchException: When Teams asked to send it later.
        :raises RuntimeDispatchException: When Microsoft couldn't be reached.
        :return: The sent message.
        """

        # Everything refused before the request, so the click isn't charged.
        integration = self.get_microsoft_integration(service)
        if integration.is_personal_account:
            raise ServiceImproperlyConfiguredDispatchException(PERSONAL_ACCOUNT_MESSAGE)

        destination_type = service.destination_type
        if destination_type not in DESTINATION_ID_FIELDS:
            raise ServiceImproperlyConfiguredDispatchException(
                "Choose whether to send the message to a channel or a chat."
            )
        ids = {}
        for field in DESTINATION_ID_FIELDS[destination_type]:
            ids[field] = resolved_values.get(field, "").strip()
            if not ids[field]:
                what = field.removesuffix("_id")
                raise ServiceImproperlyConfiguredDispatchException(
                    f"Choose the {what} to send the message to."
                )
        message = resolved_values.get("message", "")
        if not message.strip():
            raise ServiceImproperlyConfiguredDispatchException("The message is empty.")

        if destination_type == MicrosoftTeamsDestinationType.CHANNEL:
            segments = (
                "teams",
                ids["team_id"],
                "channels",
                ids["channel_id"],
                "messages",
            )
        else:
            segments = ("chats", ids["chat_id"], "messages")

        # One deadline for both the token refresh and the post.
        deadline = time.monotonic() + (
            API_OPERATION_TIMEOUT_SECONDS
            * 2
            * dispatch_context.external_request_timeouts
        )
        answer = self.graph_request(
            service,
            "POST",
            *segments,
            deadline=deadline,
            json={"body": {"contentType": "html", "content": message_to_html(message)}},
        )
        answer = answer if isinstance(answer, dict) else {}
        return {
            "message_id": str(answer.get("id") or ""),
            "created_at": answer.get("createdDateTime") or None,
            "web_url": answer.get("webUrl") or "",
            "destination_type": destination_type,
            "team_id": ids.get("team_id", ""),
            "channel_id": ids.get("channel_id", ""),
            "chat_id": ids.get("chat_id", ""),
        }

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def max_dispatch_seconds(self, service: MicrosoftTeamsWriteMessageService) -> int:
        # A token refresh and the post, each with a request timeout, doubled
        # as the Slack action does for a hang-up that lands late.
        return API_OPERATION_TIMEOUT_SECONDS * 2 * 2

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).select_related("integration")

    def get_schema_name(self, service: MicrosoftTeamsWriteMessageService) -> str:
        return f"MicrosoftTeamsWriteMessage{service.id}Schema"

    def generate_schema(
        self,
        service: MicrosoftTeamsWriteMessageService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        properties = {
            "message_id": {"type": "string", "title": _("Message ID")},
            "created_at": {
                "type": "string",
                "format": "date-time",
                "title": _("Created at"),
            },
            "web_url": {"type": "string", "title": _("Message link")},
            "destination_type": {"type": "string", "title": _("Destination type")},
            "team_id": {"type": "string", "title": _("Team ID")},
            "channel_id": {"type": "string", "title": _("Channel ID")},
            "chat_id": {"type": "string", "title": _("Chat ID")},
        }
        if allowed_fields is not None:
            properties = {
                name: value
                for name, value in properties.items()
                if name in allowed_fields
            }
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }
