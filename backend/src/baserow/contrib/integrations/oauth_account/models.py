from django.conf import settings
from django.db import models

from baserow.core.integrations.models import Integration

# The account and its tokens, as a sign-in stores them. A provider adds its own
# with `extra_connection_fields`.
BASE_CONNECTION_FIELDS = (
    "account_id",
    "account_email",
    "account_name",
    "scopes",
    "access_token",
    "refresh_token",
    "expires_at",
    "connected_at",
    "connected_by",
)
TOKEN_FIELDS = ("access_token", "refresh_token", "expires_at")


class OAuthAccountIntegrationMixin(models.Model):
    """
    An integration that holds one person's account at a provider, signed in
    through OAuth. Services act as that account with a delegated token.

    A concrete subclass declares `access_token` and `refresh_token` itself, as
    `EncryptedTextField`s with a context of its own: a context can never change
    once values are stored with it.
    """

    account_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_default="",
        help_text="The provider's stable id of the account.",
    )
    account_email = models.CharField(
        max_length=255, blank=True, default="", db_default=""
    )
    account_name = models.CharField(
        max_length=255, blank=True, default="", db_default=""
    )
    scopes = models.JSONField(
        default=list,
        db_default=[],
        help_text="The permissions the account granted, as the provider writes them.",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    generation = models.PositiveIntegerField(
        default=0,
        db_default=0,
        help_text="Changes when the account is signed out or signed in again, so "
        "a sign-in started before can tell.",
    )

    extra_connection_fields: tuple[str, ...] = ()
    """The provider's own fields a sign-in sets, e.g. a tenant id."""

    class Meta:
        abstract = True

    @classmethod
    def get_connection_fields(cls) -> list[str]:
        """
        :return: The fields a sign-in stores, which only a sign-in may set.
        """

        return [*BASE_CONNECTION_FIELDS, *cls.extra_connection_fields]

    @property
    def connected(self) -> bool:
        """
        Whether services can act as the account. A provider can add conditions,
        e.g. that its OAuth client is still the one the account signed in with.
        """

        return bool(self.refresh_token)

    @classmethod
    def get_cleared_token_values(cls) -> dict:
        """
        What forgetting the tokens sets, also used to forget them in bulk. A
        provider that stores more about a connection, e.g. a flag, adds it.

        :return: The values by field name.
        """

        return {"access_token": "", "refresh_token": "", "expires_at": None}

    def clear_tokens(self) -> list[str]:
        """
        Forget the tokens, not the account: the editor still sees who to sign
        in as again.

        :return: The fields it changed, to save.
        """

        values = self.get_cleared_token_values()
        for name, value in values.items():
            setattr(self, name, value)
        return list(values)


def lock_oauth_integration(model, integration_id: int):
    """
    Lock an integration for update and read it as stored now. Inside a
    transaction.

    Only the integration row is locked: integration updates lock that row
    before writing the provider's one, so taking both could deadlock. The
    provider's row is read after the lock is taken, in a query of its own: a
    query that joins both while waiting for the lock may return the provider's
    fields as they were before the lock holder changed them.

    :param model: The integration's model.
    :param integration_id: The integration.
    :return: The integration.
    """

    Integration.objects_and_trash.select_for_update(of=("self",)).get(id=integration_id)
    return model.objects_and_trash.get(id=integration_id)
