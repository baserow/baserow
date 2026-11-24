import time
from typing import Any, Dict, List, Optional

from django.utils import timezone
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
from baserow.core.formula.validator import ensure_array, ensure_email, ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict
from baserow_enterprise.features import MICROSOFT_OUTLOOK
from baserow_enterprise.integrations.microsoft_outlook.models import (
    MicrosoftOutlookBodyType,
    MicrosoftOutlookSendEmailService,
)
from baserow_premium.license.handler import LicenseHandler

# The Graph `contentType` of each body type.
GRAPH_CONTENT_TYPES = {
    MicrosoftOutlookBodyType.PLAIN: "Text",
    MicrosoftOutlookBodyType.HTML: "HTML",
}

# The recipient fields, with the Graph message property each fills.
RECIPIENT_FIELDS = {
    "to_emails": "toRecipients",
    "cc_emails": "ccRecipients",
    "bcc_emails": "bccRecipients",
}

# Outlook's codes for a sending limit, whatever the status they come with.
SENDING_LIMIT_CODES = {"ErrorExceededMessageLimit"}

# Outlook's codes for a recipient it can't send to.
INVALID_RECIPIENT_CODES = {
    "ErrorInvalidRecipients",
    "ErrorInvalidRecipientSubfilter",
    "ErrorRecipientTypeNotSupported",
}

NOT_ALLOWED_MESSAGE = (
    "The connected Microsoft account isn't allowed to send email. It needs an "
    "Exchange Online mailbox, and its organization must allow it to send email "
    "through Microsoft Graph."
)


def email_list(value: Any) -> List[str]:
    """
    The addresses a recipient formula resolved to, as the SMTP action reads
    them: a list, or a comma separated string.

    :param value: What the formula resolved to.
    :raises ValidationError: When an address isn't valid.
    :return: The addresses.
    """

    return [ensure_email(email) for email in ensure_array(value)]


def graph_recipients(emails: List[str]) -> List[Dict[str, Dict[str, str]]]:
    """
    :param emails: The addresses.
    :return: The Graph recipients of them.
    """

    return [{"emailAddress": {"address": email}} for email in emails]


class MicrosoftOutlookServiceTypeMixin(MicrosoftServiceTypeMixin):
    """The Microsoft permissions, license and messages of the Outlook services."""

    required_scopes = ["Mail.Send"]
    permission_description = "send email"

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(MICROSOFT_OUTLOOK, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            MICROSOFT_OUTLOOK, workspace
        )

    def api_error_exception(self, exc: ProviderAPIError) -> Exception:
        if exc.code in SENDING_LIMIT_CODES or exc.status_code == 429:
            return RemoteBusyDispatchException(
                "The connected Microsoft account reached its Outlook sending "
                "limit. Try again later."
            )
        if exc.status_code in BUSY_STATUS_CODES:
            return RemoteBusyDispatchException(
                "Outlook asked for this email to be sent again later."
            )
        # Outlook's own codes first: they say more than the status they come with.
        if exc.code == "ErrorMessageSubmissionBlocked":
            return RemoteRefusedDispatchException(
                "Microsoft blocked the connected account from sending email, "
                "often after suspected spam. An admin of its organization can "
                "unblock it."
            )
        if exc.code in INVALID_RECIPIENT_CODES:
            return RemoteRefusedDispatchException(
                "Outlook refused a recipient of this email. Check that each "
                "address is valid."
            )
        if exc.status_code in (400, 413):
            return RemoteRefusedDispatchException(
                "Outlook refused this email as malformed or too large "
                f"({exc.code or exc.status_code}). Check the recipients, subject "
                "and body."
            )
        # `/me/sendMail` names nothing else that could be missing: a 404 is an
        # account with no mailbox, e.g. without an Exchange Online license.
        if exc.status_code in (403, 404):
            return RemoteRefusedDispatchException(NOT_ALLOWED_MESSAGE)
        return super().api_error_exception(exc)


class MicrosoftOutlookSendEmailServiceType(
    MicrosoftOutlookServiceTypeMixin, ServiceType
):
    type = "microsoft_outlook_send_email"
    model_class = MicrosoftOutlookSendEmailService
    dispatch_types = [DispatchTypes.ACTION]
    is_external = True

    allowed_fields = [
        "integration_id",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body_type",
        "body",
    ]
    serializer_field_names = allowed_fields
    simple_formula_fields = ["to_emails", "cc_emails", "bcc_emails", "subject", "body"]
    # Who the email goes to and what it says, as for the SMTP action: a literal
    # recipient is somebody's personal data.
    sensitive_fields = simple_formula_fields

    class SerializedDict(ServiceDict):
        to_emails: BaserowFormulaObject
        cc_emails: BaserowFormulaObject
        bcc_emails: BaserowFormulaObject
        subject: BaserowFormulaObject
        body_type: str
        body: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        def help_text(name):
            return MicrosoftOutlookSendEmailService._meta.get_field(name).help_text

        return {
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the Microsoft integration.",
            ),
            **{
                name: FormulaSerializerField(required=False, help_text=help_text(name))
                for name in self.simple_formula_fields
            },
            "body_type": serializers.ChoiceField(
                choices=MicrosoftOutlookBodyType.choices,
                required=False,
                help_text=help_text("body_type"),
            ),
        }

    def get_configuration_errors(
        self, service: MicrosoftOutlookSendEmailService
    ) -> dict[str, str]:
        if not (service.to_emails or {}).get("formula", "").strip():
            return {"to_emails": "required"}
        return {}

    def formulas_to_resolve(
        self, service: MicrosoftOutlookSendEmailService
    ) -> list[FormulaToResolve]:
        return [
            *[
                FormulaToResolve(
                    field, getattr(service, field), email_list, f'property "{field}"'
                )
                for field in RECIPIENT_FIELDS
            ],
            FormulaToResolve(
                "subject", service.subject, ensure_string, 'property "subject"'
            ),
            FormulaToResolve("body", service.body, ensure_string, 'property "body"'),
        ]

    def dispatch(
        self,
        service: MicrosoftOutlookSendEmailService,
        dispatch_context: DispatchContext,
    ) -> DispatchResult:
        self.raise_if_deactivated(dispatch_context.workspace)
        return super().dispatch(service, dispatch_context)

    def dispatch_data(
        self,
        service: MicrosoftOutlookSendEmailService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Sends the email from the integration's account. Outlook accepts it for
        delivery without saying whether it was delivered, nor its message id.

        :raises ServiceImproperlyConfiguredDispatchException: When its account
            can't be used.
        :raises InvalidContextContentDispatchException: When it has no
            recipient.
        :raises RemoteRefusedDispatchException: When Outlook refused the email.
        :raises RemoteBusyDispatchException: When Outlook asked to send it later.
        :raises RuntimeDispatchException: When Microsoft couldn't be reached.
        :return: What was submitted.
        """

        # Everything refused before the request, so the click isn't charged.
        integration = self.get_microsoft_integration(service)
        recipients = {
            field: resolved_values.get(field) or [] for field in RECIPIENT_FIELDS
        }
        if not recipients["to_emails"]:
            raise InvalidContextContentDispatchException(
                "At least one recipient email is required."
            )
        subject = resolved_values.get("subject", "")
        body = resolved_values.get("body", "")
        body_type = (
            service.body_type
            if service.body_type in GRAPH_CONTENT_TYPES
            else MicrosoftOutlookBodyType.PLAIN
        )

        message = {
            "subject": subject,
            "body": {"contentType": GRAPH_CONTENT_TYPES[body_type], "content": body},
        }
        for field, graph_field in RECIPIENT_FIELDS.items():
            if recipients[field]:
                message[graph_field] = graph_recipients(recipients[field])

        # One deadline for both the token refresh and the send.
        deadline = time.monotonic() + (
            API_OPERATION_TIMEOUT_SECONDS
            * 2
            * dispatch_context.external_request_timeouts
        )
        # Answers 202 with no body: accepted for delivery, not delivered.
        self.graph_request(
            service,
            "POST",
            "me",
            "sendMail",
            deadline=deadline,
            json={"message": message, "saveToSentItems": True},
        )
        return {
            "submitted": True,
            "submitted_at": timezone.now().isoformat(),
            "from_email": integration.account_email,
            **recipients,
            "subject": subject,
        }

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def max_dispatch_seconds(self, service: MicrosoftOutlookSendEmailService) -> int:
        # A token refresh and the send, each with a request timeout, doubled
        # as the Slack action does for a hang-up that lands late.
        return API_OPERATION_TIMEOUT_SECONDS * 2 * 2

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).select_related("integration")

    def get_schema_name(self, service: MicrosoftOutlookSendEmailService) -> str:
        return f"MicrosoftOutlookSendEmail{service.id}Schema"

    def generate_schema(
        self,
        service: MicrosoftOutlookSendEmailService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        def email_list_schema(title):
            return {"type": "array", "title": title, "items": {"type": "string"}}

        properties = {
            "submitted": {
                "type": "boolean",
                "title": _("Submitted"),
                "description": _(
                    "Whether Outlook accepted the email for delivery. It doesn't "
                    "say whether it was delivered."
                ),
            },
            "submitted_at": {
                "type": "string",
                "format": "date-time",
                "title": _("Submitted at"),
            },
            "from_email": {"type": "string", "title": _("From")},
            "to_emails": email_list_schema(_("To")),
            "cc_emails": email_list_schema(_("CC")),
            "bcc_emails": email_list_schema(_("BCC")),
            "subject": {"type": "string", "title": _("Subject")},
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
