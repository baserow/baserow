from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.utils import timezone

import pytest

from baserow.contrib.database.search.handler import SearchHandler


@pytest.fixture
def populate_search_table():
    """
    Returns a helper that creates a workspace search table and inserts
    tsvector rows for every non-empty cell in the given rows / field.
    """

    def _populate(table, field, rows):
        workspace = table.database.workspace
        SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
        search_model = SearchHandler.get_workspace_search_table_model(workspace.id)

        model = table.get_model()
        for row in rows:
            row_obj = model.objects.get(id=row.id)
            cell_value = getattr(row_obj, field.db_column)
            if cell_value:
                search_model.objects.create(
                    row_id=row_obj.id,
                    field_id=field.id,
                    updated_on=timezone.now(),
                    value=SearchVector(Value(str(cell_value))),
                )

        return search_model

    return _populate
