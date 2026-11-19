import base64
from copy import copy
from email.message import EmailMessage
from email.policy import SMTP

from django.utils.translation import gettext as _

from rest_framework import serializers

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

from . import oauth
from .models import GoogleGmailSendEmailService, GoogleIntegration


class GoogleGmailSendEmailServiceType(ServiceType):
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
    required_scopes = [oauth.GMAIL_SEND_SCOPE]
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
        credential_id = (
            service.integration.specific.credential_source_id or service.integration_id
        )
        token, sender = oauth.access_token(credential_id, self.required_scopes)
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
        status, data = oauth.request_json(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw},
        )
        if status == 401:
            oauth.invalidate_access_token(credential_id, token)
            raise RemoteRefusedDispatchException(
                "Google authorization was refused. Reconnect the integration."
            )
        if status == 403:
            details = data.get("error")
            details = details if isinstance(details, dict) else {}
            errors = details.get("errors", [])
            errors = errors if isinstance(errors, list) else []
            reasons = {
                item.get("reason")
                for item in errors
                if isinstance(item, dict) and isinstance(item.get("reason"), str)
            }
            if reasons & {
                "rateLimitExceeded",
                "userRateLimitExceeded",
                "dailyLimitExceeded",
            }:
                raise RemoteBusyDispatchException(
                    "The Gmail sending quota was exceeded."
                )
            raise RemoteRefusedDispatchException(
                "Google refused permission to send. Check consent and enable Gmail API."
            )
        if status == 400:
            raise RemoteRefusedDispatchException(
                "Gmail rejected the message or its recipients."
            )
        if (
            status != 200
            or not isinstance(data.get("id"), str)
            or not isinstance(data.get("threadId"), str)
        ):
            raise RemoteRefusedDispatchException(
                "Gmail returned an invalid send response."
            )
        return {"id": data["id"], "threadId": data["threadId"]}

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
        return oauth.REQUEST_TIMEOUT * 4
