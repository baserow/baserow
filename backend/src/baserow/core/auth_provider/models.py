from django.contrib.contenttypes.models import ContentType
from django.db import connection, models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
)
from baserow.core.psycopg import sql


class BaseAuthProviderModel(
    CreatedAndUpdatedOnMixin, PolymorphicContentTypeMixin, models.Model, WithRegistry
):
    """
    Base abstract model for app_providers.
    """

    domain = models.CharField(
        max_length=255,
        null=True,
        help_text="The email domain registered with this provider.",
    )
    enabled = models.BooleanField(
        help_text="Whether the provider is enabled or not.", default=True
    )

    class Meta:
        abstract = True


class AuthProviderModel(BaseAuthProviderModel):
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="auth_providers",
        on_delete=models.CASCADE,
    )

    users = models.ManyToManyField(
        "auth.User",
        related_name="auth_providers",
        help_text=("The users that have been authenticated with this provider."),
    )

    @staticmethod
    def get_type_registry():
        from baserow.core.registries import auth_provider_type_registry

        return auth_provider_type_registry

    def user_signed_in(self, user):
        """
        This method is called when a user has successfully signed in with this
        authentication provider. It can be used to update the user model with
        information from the authentication provider.

        :param user: The user that has signed in.
        """

        self.users.add(user)

    @classmethod
    def get_next_provider_id(cls) -> int:
        """
        Returns the next provider id so that the callback URL
        can be guessed before the provider is created.
        """

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT last_value + 1 from {table_id_seq};").format(
                    table_id_seq=sql.Identifier(f"{cls._meta.db_table}_id_seq")
                )
            )
            return int(cursor.fetchone()[0])

    class Meta:
        ordering = ["domain"]


class PasswordAuthProviderModel(AuthProviderModel):
    ...
