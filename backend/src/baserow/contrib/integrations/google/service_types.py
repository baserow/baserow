import base64
from copy import copy
from email.message import EmailMessage
from email.policy import SMTP

from django.utils.translation import gettext as _

from rest_framework import serializers

from baserow.contrib.integrations.oauth_account.service_types import (
    OAuthAccountServiceTypeMixin,
)
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.validator import ensure_array, ensure_email, ensure_string
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict

from .models import GoogleGmailSendEmailService, GoogleIntegration
from .providers import GMAIL_SEND_SCOPE


class GoogleGmailSendEmailServiceType(OAuthAccountServiceTypeMixin, ServiceType):
    class SerializedDict(ServiceDict):
        to_emails: dict
        cc_emails: dict
        bcc_emails: dict
        subject: dict
        body: dict
        body_type: str

    type = "google_gmail_send_email"
    model_class = GoogleGmailSendEmailService
    dispatch_types = [DispatchTypes.ACTION]
    integration_type = "google"
    required_scopes = [GMAIL_SEND_SCOPE]
    permission_description = "send Gmail messages"
    is_external = True
    simple_formula_fields = ["to_emails", "cc_emails", "bcc_emails", "subject", "body"]
    sensitive_fields = simple_formula_fields
    allowed_fields = ["integration_id", *simple_formula_fields, "body_type"]
    serializer_field_names = allowed_fields
    public_serializer_field_names = allowed_fields

    @property
    def serializer_field_overrides(self):
        """Expose composer formulas and validate the supported MIME body types."""
        return {
            "integration_id": serializers.IntegerField(required=False, allow_null=True),
            **{name: FormulaSerializerField() for name in self.simple_formula_fields},
            "body_type": serializers.ChoiceField(
                choices=["plain", "html"], default="plain", required=False
            ),
        }

    @property
    def public_serializer_field_overrides(self):
        return self.serializer_field_overrides

    def formulas_to_resolve(self, service):
        """Use the same recipient resolution and validation as SMTP actions."""
        return [
            FormulaToResolve(
                name,
                getattr(service, name),
                (lambda value: [ensure_email(email) for email in ensure_array(value)])
                if name.endswith("_emails")
                else ensure_string,
                f'property "{name}"',
            )
            for name in self.simple_formula_fields
        ]

    def requires_autocommit(self, service):
        # Builder actions must not wrap token refresh and sending in one transaction.
        return True

    def dispatch(self, service, dispatch_context):
        """Keep refreshed credentials committed even when sending subsequently fails."""
        context = copy(dispatch_context)
        context.sends_external_calls_outside_transaction = True
        return super().dispatch(service, context)

    def dispatch_data(self, service, resolved_values, dispatch_context):
        """Send once: an ambiguous network failure must never resend automatically."""
        if not service.integration_id or not isinstance(
            service.integration.specific, GoogleIntegration
        ):
            raise ServiceImproperlyConfiguredDispatchException(
                "Select a Google integration."
            )
        if not resolved_values["to_emails"]:
            raise InvalidContextContentDispatchException(
                "At least one recipient email is required."
            )
        sender = self.get_oauth_integration(service).account_email
        message = EmailMessage(policy=SMTP)
        try:
            message["From"] = sender
            message["Subject"] = resolved_values["subject"]
            for header, field in (
                ("To", "to_emails"),
                ("Cc", "cc_emails"),
                ("Bcc", "bcc_emails"),
            ):
                if resolved_values[field]:
                    message[header] = ", ".join(resolved_values[field])
            message.set_content(resolved_values["body"], subtype=service.body_type)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        except (ValueError, TypeError):
            raise InvalidContextContentDispatchException(
                "Invalid email headers or body."
            ) from None
        response = self.request_as_account(
            service,
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json={"raw": raw},
        )
        try:
            data = response.json()
        except ValueError:
            raise RemoteRefusedDispatchException(
                "Gmail returned an invalid send response."
            ) from None
        if (
            response.status_code != 200
            or not isinstance(data, dict)
            or not isinstance(data.get("id"), str)
            or not isinstance(data.get("threadId"), str)
        ):
            raise RemoteRefusedDispatchException(
                "Gmail returned an invalid send response."
            )
        return {"id": data["id"], "threadId": data["threadId"]}

    def get_api_error_code(self, response):
        """Extract Gmail reason codes for the shared transport error mapper."""
        try:
            payload = response.json()
        except ValueError:
            return ""
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        errors = error.get("errors", []) if isinstance(error, dict) else []
        for detail in errors if isinstance(errors, list) else []:
            if isinstance(detail, dict) and isinstance(detail.get("reason"), str):
                return detail["reason"]
        return ""

    def api_error_exception(self, exc):
        """Classify Gmail quotas and invalid messages alongside shared HTTP errors."""
        if exc.status_code == 403 and exc.code in {
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "dailyLimitExceeded",
        }:
            return RemoteBusyDispatchException("The Gmail sending quota was exceeded.")
        if exc.status_code == 400:
            return RemoteRefusedDispatchException(
                "Gmail rejected the message or its recipients."
            )
        return super().api_error_exception(exc)

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def get_schema_name(self, service):
        return f"GoogleGmailSendEmail{service.id}Schema"

    def generate_schema(self, service, allowed_fields=None):
        """Describe the exact result available to formulas after sending."""
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                name: {
                    "type": "string",
                    "title": title,
                    "examples": ["18f0a1b2c3d4e5f6"],
                }
                for name, title in [
                    ("id", _("Message ID")),
                    ("threadId", _("Thread ID")),
                ]
                if allowed_fields is None or name in allowed_fields
            },
        }

    def max_dispatch_seconds(self, service):
        return 80
