import time

from django.db.models import Count

import pytest

from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.vector_table import SemanticSearchVectorTable

# Search data updates are deferred in tests by default, but they're how changed
# cells reach the semantic search index.
enable_search_data_updates = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay"
)


def get_chunk_counts(field) -> dict[int, int]:
    """Returns the number of chunks per row of the field."""

    vector_table = SemanticSearchVectorTable(field.table.database.workspace_id)
    if not vector_table.exists():
        return {}
    return dict(
        vector_table.model.objects.filter(field_id=field.id)
        .values("row_id")
        .annotate(count=Count("id"))
        .values_list("row_id", "count")
    )


def get_chunk_texts(field) -> set[tuple[str | None, str | None]]:
    """Returns the `(content, source)` of the stored chunks of the field."""

    vector_table = SemanticSearchVectorTable(field.table.database.workspace_id)
    return set(
        vector_table.model.objects.filter(field_id=field.id).values_list(
            "content", "source"
        )
    )


def index(table, seconds: float = 60) -> bool:
    return SemanticSearchHandler().index_table(table, time.monotonic() + seconds)
