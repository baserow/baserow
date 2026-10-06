from django.db import models

from baserow.core.integrations.models import Integration

CREDENTIAL_FIELDS = ("client_id", "client_secret")
TOKEN_FIELDS = (
    "refresh_token",
    "access_token",
    "access_token_expires_at",
    "account_email",
)


class OAuth2Integration(Integration):
    """
    An integration that acts as an account the user connected through the
    provider's consent screen. The app registration (client id and secret) is
    the user's own, so no instance-wide configuration is needed.
    """

    client_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The client id of the OAuth app registered with the provider.",
    )
    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The client secret of the OAuth app.",
    )
    refresh_token = models.TextField(
        blank=True,
        default="",
        help_text="Issued when the account was connected; used to mint access tokens.",
    )
    access_token = models.TextField(blank=True, default="")
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    account_email = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The email address of the connected account, for display.",
    )

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_credentials = self._credentials()

    def _credentials(self):
        return tuple(getattr(self, name) for name in CREDENTIAL_FIELDS)

    def save(self, *args, **kwargs):
        # Tokens belong to the app registration they were issued for, so a new
        # client id or secret disconnects the account.
        if self.pk and self._credentials() != self._loaded_credentials:
            self.refresh_token = ""
            self.access_token = ""
            self.access_token_expires_at = None
            self.account_email = ""
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list({*update_fields, *TOKEN_FIELDS})
        super().save(*args, **kwargs)
        self._loaded_credentials = self._credentials()

    @property
    def is_connected(self) -> bool:
        return bool(self.refresh_token)
