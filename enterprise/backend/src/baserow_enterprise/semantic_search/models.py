from django.db import models

from pgvector.django import VectorField

from baserow.contrib.database.search.models import AbstractPendingSearchDataUpdate
from baserow.core.pgvector import DEFAULT_EMBEDDING_DIMENSIONS


class SemanticSearchField(models.Model):
    """
    Exists for every field that has semantic search enabled. Deleting it disables
    semantic search for the field.
    """

    class Status(models.TextChoices):
        INDEXING = "indexing"
        READY = "ready"
        ERROR = "error"

    field = models.OneToOneField(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="semantic_search",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.INDEXING,
    )


class SemanticSearchPendingUpdateManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deletion_workspace_id=None)


class SemanticSearchPendingUpdate(AbstractPendingSearchDataUpdate):
    copy_vectors_from_field_id = models.PositiveIntegerField(
        null=True,
        help_text="A field with the same rows of which the vectors are copied before "
        "an update of all rows, so that unchanged values aren't embedded again.",
    )
    processed_until_row_id = models.PositiveIntegerField(
        null=True,
        help_text="Allows an update of all rows to continue where it stopped.",
    )
    deletion_workspace_id = models.IntegerField(
        null=True,
        help_text="The workspace ID used to mark the vectors of the field or row for "
        "deletion once its table, field or row is permanently deleted, or semantic "
        "search is disabled.",
    )

    objects = SemanticSearchPendingUpdateManager()
    objects_and_trash = models.Manager()

    class Meta(AbstractPendingSearchDataUpdate.Meta):
        indexes = [
            models.Index(
                fields=["deletion_workspace_id", "field_id", "row_id"],
                name="semanticsearchdeletion_idx",
                condition=models.Q(deletion_workspace_id__isnull=False),
            ),
        ]


class AbstractSemanticSearchChunk(models.Model):
    """
    A chunk of the text of a cell and its embedding. The chunks of all semantic search
    fields of a workspace are stored in one table per workspace.
    """

    id = models.BigAutoField(primary_key=True)
    field_id = models.IntegerField()
    row_id = models.IntegerField()
    chunk_index = models.SmallIntegerField()
    content_hash = models.CharField(
        max_length=32,
        help_text="The hash of the indexed value of the cell, so that unchanged values "
        "aren't embedded again.",
    )
    embedding = VectorField(dimensions=DEFAULT_EMBEDDING_DIMENSIONS)

    class Meta:
        abstract = True
