from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from django.db import OperationalError, close_old_connections, connections

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.handler import ViewIndexingHandler


def _update_index_on_another_connection(view_id):
    close_old_connections()
    try:
        ViewIndexingHandler.update_index_by_view_id(view_id)
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("existing_index", [False, True])
def test_field_conversion_blocks_index_worker_until_schema_is_ready(
    data_fixture, existing_index
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO", date_time_format="24"
    )
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_sort(view=view, field=field, order="ASC")
    model = table.get_model()
    row = model.objects.create(
        **{field.db_column: datetime(2024, 1, 8, 9, 30, tzinfo=timezone.utc)}
    )
    if existing_index:
        ViewIndexingHandler.update_index(view, model)
    # The grouping is saved while its index creation is still queued. A worker
    # would now replace the raw timestamp index, or create the first view index.
    data_fixture.create_view_group_by(view=view, field=field, order="ASC")
    drop_indexes = ViewIndexingHandler.drop_all_indexes_for_table

    with ThreadPoolExecutor(max_workers=1) as executor:

        def drop_while_worker_attempts_update(table_id):
            worker = executor.submit(_update_index_on_another_connection, view.id)
            with pytest.raises(OperationalError, match="could not obtain lock"):
                worker.result(timeout=10)
            drop_indexes(table_id)

        with patch.object(
            ViewIndexingHandler,
            "drop_all_indexes_for_table",
            side_effect=drop_while_worker_attempts_update,
        ) as cleanup:
            # No caller transaction: the handler must retain its table lock until
            # both index cleanup and the column conversion have finished.
            field = FieldHandler().update_field(user, field, new_type_name="text")
            cleanup.assert_called_once_with(table.id)

        # Retry from a fresh view/model snapshot, as the queued task does.
        executor.submit(_update_index_on_another_connection, view.id).result(timeout=10)

    view.refresh_from_db()
    model = table.get_model()
    index = ViewIndexingHandler.get_index(view, model)
    assert view.db_index_name == index.name
    assert ViewIndexingHandler.does_index_exist(index.name)
    assert getattr(model.objects.get(id=row.id), field.db_column) == "2024-01-08 09:30"
