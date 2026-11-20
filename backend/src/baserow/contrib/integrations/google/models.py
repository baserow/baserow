from django.db import models

from baserow.core.fields import EncryptedTextField, is_unreadable_secret
from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service


class GoogleIntegration(Integration):
    credential_source = models.ForeignKey(
        "self", null=True, on_delete=models.SET_NULL, related_name="publications"
    )
    client_mode = models.CharField(
        max_length=16,
        choices=[("default", "Baserow"), ("custom", "Custom")],
        default="custom",
    )
    client_id = models.CharField(max_length=2000, blank=True, default="")
    client_secret = EncryptedTextField(
        context="integrations.google.client_secret", blank=True, default=""
    )
    access_token = EncryptedTextField(
        context="integrations.google.access_token", blank=True, default=""
    )
    refresh_token = EncryptedTextField(
        context="integrations.google.refresh_token", blank=True, default=""
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    account_id = models.CharField(max_length=255, blank=True, default="")
    account_email = models.EmailField(blank=True, default="")
    granted_scopes = models.JSONField(default=list)
    generation = models.PositiveIntegerField(default=0)
    connected = models.BooleanField(default=False)
    connected_client = models.CharField(max_length=64, blank=True, default="")

    @property
    def is_connected(self):
        from .oauth import client_fingerprint

        if any(
            is_unreadable_secret(value)
            for value in (self.client_secret, self.access_token, self.refresh_token)
        ):
            return False
        return self.connected and self.connected_client == client_fingerprint(self)

    def clear_tokens(self):
        self.access_token = ""
        self.refresh_token = ""
        self.expires_at = None
        self.granted_scopes = []
        self.connected = False
        self.connected_client = ""


class GoogleGmailSendEmailService(Service):
    to_emails = FormulaField(help_text="Recipient email addresses.")
    cc_emails = FormulaField(blank=True, help_text="CC email addresses.")
    bcc_emails = FormulaField(blank=True, help_text="BCC email addresses.")
    subject = FormulaField(help_text="The email subject.")
    body = FormulaField(help_text="The email body.")
    body_type = models.CharField(
        max_length=10,
        choices=[("plain", "Plain text"), ("html", "HTML")],
        default="plain",
    )
