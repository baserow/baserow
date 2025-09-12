from functools import cached_property

from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
)


class FieldRule(
    CreatedAndUpdatedOnMixin, PolymorphicContentTypeMixin, models.Model, WithRegistry
):
    table = models.ForeignKey(
        "database.Table",
        null=False,
        on_delete=models.CASCADE,
        related_name="field_rules",
        related_query_name="field_rules",
        help_text="The table that this field rule applies to.",
    )
    is_active = models.BooleanField(
        null=False, default=True, help_text="Allows to enable/disable a field rule."
    )
    is_valid = models.BooleanField(
        null=False,
        default=True,
        help_text="Tells if the rule is valid in the context of a table. This field is read-only.",
    )
    error_text = models.TextField(
        null=True,
        help_text="Stores information about validation error, if it's present. This field is read-only.",
    )

    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="field_rule",
        on_delete=models.CASCADE,
    )

    @cached_property
    def type(self):
        return self.get_type().type

    @staticmethod
    def get_type_registry():
        """Returns the registry related to this model class."""

        from baserow.contrib.database.field_rules.registries import (
            field_rules_type_registry,
        )

        return field_rules_type_registry

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "table_id": self.table_id,
            "type": self.get_type().type,
            "is_active": self.is_active,
            "is_valid": self.is_valid,
            "error_text": self.error_text,
        }
