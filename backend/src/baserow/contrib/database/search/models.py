from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from django_cte import CTEManager


class PendingSearchValueUpdateTrashManager(CTEManager):
    def get_queryset(self):
        return super().get_queryset().filter(models.Q(deletion_workspace_id=None))


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
    # DEPRECATED: Remove this FK in future versions. Use `field_id` instead.
    table = models.ForeignKey(
        "database.Table", on_delete=models.CASCADE, related_name="+", null=True
    )
    field_id = models.IntegerField(
        help_text="The ID of the field to update.",
    )
    row_id = models.IntegerField(
        null=True,
        help_text="The ID of the row to update. If null, all table rows will be updated.",
    )
    updated_on = models.DateTimeField(
        auto_now=True,
        db_default=models.functions.Now(),
        help_text="The time this update was last modified.",
    )
    deletion_workspace_id = models.IntegerField(
        null=True,
        help_text=(
            "The workspace ID used to mark this pending update for deletion "
            "once its associated table, field or row is permanently removed."
        ),
    )

    objects = PendingSearchValueUpdateTrashManager()
    objects_and_trash = CTEManager()

    class Meta:
        # Avoid duplicate entries for the same field and row.
        unique_together = [("field_id", "row_id")]

        indexes = [
            # Speed up deletion of pending updates
            models.Index(
                fields=["deletion_workspace_id", "field_id", "row_id"],
                name="pendingsearchvaluedeletion_idx",
                condition=models.Q(deletion_workspace_id__isnull=False),
            ),
            # This speeds up `field_id__in=[... many field IDS...]`.
            models.Index(
                name="pendingsearchvaluedeletion_ord",
                fields=["-updated_on"],
            ),
            # This speeds up `field_id__in=[... few field IDS...]`.
            models.Index(
                name="pendingsearchvaluedeletion_frd",
                fields=["field_id", "-updated_on"],
            ),
        ]


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
