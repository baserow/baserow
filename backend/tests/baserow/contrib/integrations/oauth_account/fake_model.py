"""
A test-only integration model, for the OAuth account base's tests. It's
imported only by the `fake_oauth_table` fixture, which creates its table first:
once a model is registered, deleting users or applications looks for its rows,
so it must never be registered without its table.
"""

from django.db import models

from baserow.contrib.integrations.oauth_account.models import (
    OAuthAccountIntegrationMixin,
)
from baserow.core.fields import EncryptedTextField
from baserow.core.integrations.models import Integration


class FakeOAuthIntegration(OAuthAccountIntegrationMixin, Integration):
    access_token = EncryptedTextField(
        context="integrations.fakeoauthintegration.access_token",
        blank=True,
        default="",
        db_default="",
    )
    refresh_token = EncryptedTextField(
        context="integrations.fakeoauthintegration.refresh_token",
        blank=True,
        default="",
        db_default="",
    )
    # A provider's own connection field, e.g. a tenant.
    tenant = models.CharField(max_length=64, blank=True, default="", db_default="")
    # An OAuth client of the integration's own, for providers that offer one.
    own_client_id = models.CharField(max_length=255, blank=True, default="")
    own_client_secret = models.CharField(max_length=255, blank=True, default="")

    extra_connection_fields = ("tenant",)

    class Meta:
        app_label = "integrations"
