from django.db import models

from baserow.contrib.integrations.oauth_account.models import (
    OAuthAccountIntegrationMixin,
)
from baserow.core.fields import EncryptedTextField
from baserow.core.integrations.models import Integration

# The tenant every personal Microsoft account signs in from.
PERSONAL_ACCOUNT_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"


class MicrosoftIntegration(OAuthAccountIntegrationMixin, Integration):
    """
    One Microsoft account, signed in through the instance's Entra app. Services
    act as that account with a delegated token, asked for with the permissions
    they need when they need them.
    """

    tenant_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_default="",
        help_text="The tenant (`tid`) the account signed in from.",
    )
    access_token = EncryptedTextField(
        context="integrations.microsoftintegration.access_token",
        blank=True,
        default="",
        db_default="",
    )
    refresh_token = EncryptedTextField(
        context="integrations.microsoftintegration.refresh_token",
        blank=True,
        default="",
        db_default="",
    )

    extra_connection_fields = ("tenant_id",)

    @property
    def is_personal_account(self) -> bool:
        return self.tenant_id == PERSONAL_ACCOUNT_TENANT_ID

    @property
    def account_type(self) -> str:
        if not self.account_id:
            return ""
        return "personal" if self.is_personal_account else "work_or_school"
