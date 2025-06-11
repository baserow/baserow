from collections.abc import Iterator
from typing import NamedTuple

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from django_cte import CTEManager


class IndexDescription(NamedTuple):
    fields: Iterator[str]
    name: str
    type: str

    def get_name(self, for_table_id: int) -> str:
        return self.name.format(for_table_id)


class SearchTableBase(models.Model):
    """
    Abstract base model for a search table.
    """

    # Should be increased by 1 after each change. remember about indexes!
    version = 1
    parent = None

    class Meta:
        abstract = True
        managed = False

    # Ideally, this table should not have a primary key, but since Django ORM requires
    # one to be present, and this table can grow even for small workspaces, primary key
    # field should provide sufficient value space here.
    id = models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )
    row_id = models.IntegerField(null=False)
    field_id = models.IntegerField(null=False)
    updated_on = models.DateTimeField(auto_now_add=True, auto_now=True, null=False)
    value = SearchVectorField(null=False)
    objects = CTEManager()

    def get_parent(self):
        return self.parent


def get_search_indexes(workspace_id: int) -> list[models.Index]:
    """
    Build Indexes with names related to a table
    """

    indexes = [
        models.Index(
            fields=(
                "field_id",
                "row_id",
                "updated_on",
            ),
            name=f"database_workspace_{workspace_id}_search_field_updated_on_idx",
        ),
        models.Index(
            fields=("field_id",),
            name=f"database_workspace_{workspace_id}_field_id_idx",
        ),
        GinIndex(
            fields=("value",),
            name=f"database_workspace_{workspace_id}_value_tsv_idx",
        ),
    ]
    return indexes
