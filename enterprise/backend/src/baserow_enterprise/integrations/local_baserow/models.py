from django.contrib.auth import get_user_model
from django.db import models

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowFilterableServiceMixin,
    LocalBaserowViewService,
)
from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.formula.field import FormulaField
from baserow.core.user_sources.models import UserSource

User = get_user_model()


class LocalBaserowUserSource(UserSource):
    """
    This model represents the Local baserow user source. This source save user accounts
    in a database table of the same instance.
    """

    table = models.ForeignKey(Table, null=True, default=None, on_delete=models.SET_NULL)

    email_field = models.ForeignKey(
        Field,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The Baserow field that contains the email value for the user.",
    )

    name_field = models.ForeignKey(
        Field,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The Baserow field that contains the name of the user.",
    )

    role_field = models.ForeignKey(
        Field,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The Baserow field that contains the role of the user.",
    )


class LocalBaserowPasswordAppAuthProvider(AppAuthProvider):
    password_field = models.ForeignKey(
        Field,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The Baserow field that contains the password of the user.",
    )

    @property
    def is_configured(self) -> bool:
        """
        Returns whether the authentication provider is configured properly.
        """

        return self.get_type().is_configured(self)


class LocalBaserowSemanticSearch(
    LocalBaserowViewService, LocalBaserowFilterableServiceMixin
):
    # Kept apart from an empty `search_fields`, because when every chosen field is
    # deleted, the search must not widen to the fields that were left out.
    search_all_fields = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Searches every field with semantic search enabled.",
    )
    search_fields = models.ManyToManyField(
        Field,
        related_name="+",
        help_text="The fields with semantic search enabled to search in, when not "
        "all of them are searched.",
    )
    included_fields = models.ManyToManyField(
        Field,
        related_name="+",
        help_text="The fields of which the values are returned. All when empty.",
    )
    search_query = FormulaField(default="", help_text="The text to search for.")
    max_results = models.PositiveSmallIntegerField(
        default=10, help_text="The maximum number of rows to return."
    )
    min_similarity = models.FloatField(
        null=True,
        help_text="Rows of which the meaning is less similar to the query are left "
        "out. Between 0 and 1.",
    )

    @property
    def search_field_ids(self) -> list[int]:
        return sorted(field.id for field in self.search_fields.all())

    @property
    def included_field_ids(self) -> list[int]:
        return sorted(field.id for field in self.included_fields.all())
