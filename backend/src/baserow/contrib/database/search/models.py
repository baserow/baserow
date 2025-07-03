from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from django_cte import CTEManager


class PendingSearchValueUpdate(models.Model):
    """
    A table to collect pending updates for TSVector values.
    """

    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        serialize=False,
        verbose_name="ID",
    )
    table = models.ForeignKey("database.Table", on_delete=models.CASCADE)
    field_id = models.IntegerField(
        help_text="The ID of the field to update.",
    )
    row_id = models.IntegerField(
        null=True,
        help_text="The ID of the row to update. If null, all rows will be updated.",
    )

    class Meta:
        ordering = ["-id"]
        # Avoid duplicate entries for the same field and row.
        unique_together = ("field_id", "row_id")


class AbstractSearchValue(models.Model):
    """
    Abstract base model for a table containing TSVector search data,
    keyed by (row_id, field_id) and holding the TSVector in `value`.
    """

    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        serialize=False,
        verbose_name="ID",
    )
    row_id = models.IntegerField(
        help_text="The ID of the row this value belongs to.",
    )
    field_id = models.IntegerField(
        help_text="The ID of the field this value belongs to."
    )
    updated_on = models.DateTimeField(
        help_text="The time this value was last updated.",
    )
    value = SearchVectorField(
        help_text="The full-text search vector value to index and use for searching."
    )
    objects = CTEManager()

    class Meta:
        abstract = True
        unique_together = ("field_id", "row_id")


def get_search_indexes(workspace_id: int) -> list[models.Index]:
    """
    Build Indexes with names related to a table
    """

    indexes = [
        GinIndex(
            fields=("value",),
            name=f"database_workspace_{workspace_id}_value_tsv_idx",
        )
    ]
    return indexes
