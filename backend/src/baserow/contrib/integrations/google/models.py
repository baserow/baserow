from django.db import models

from baserow.contrib.integrations.oauth_account.models import (
    OAuthAccountIntegrationMixin,
)
from baserow.core.fields import EncryptedTextField
from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service


class GoogleIntegration(OAuthAccountIntegrationMixin, Integration):
    client_mode = models.CharField(
        max_length=16,
        choices=[("default", "Baserow"), ("custom", "Custom")],
        default="custom",
        db_default="custom",
    )
    client_id = models.CharField(max_length=2000, blank=True, default="", db_default="")
    client_secret = EncryptedTextField(
        context="integrations.google.client_secret",
        blank=True,
        default="",
        db_default="",
    )
    access_token = EncryptedTextField(
        context="integrations.google.access_token",
        blank=True,
        default="",
        db_default="",
    )
    refresh_token = EncryptedTextField(
        context="integrations.google.refresh_token",
        blank=True,
        default="",
        db_default="",
    )
    connected_client = models.CharField(
        max_length=64, blank=True, default="", db_default=""
    )
    extra_connection_fields = ("connected_client",)

    @property
    def connected(self):
        from .providers import GoogleOAuthProvider

        client = GoogleOAuthProvider().get_client(self)
        return bool(
            super().connected and client and self.connected_client == client.fingerprint
        )

    @classmethod
    def get_cleared_token_values(cls):
        return {**super().get_cleared_token_values(), "connected_client": ""}


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
