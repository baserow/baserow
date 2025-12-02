import pytest
from freezegun import freeze_time

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.models import PendingSearchValueUpdate
from baserow.contrib.database.search.tasks import periodic_check_pending_search_data

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)


@pytest.mark.django_db(transaction=True)
def test_periodic_check_pending_search_data(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)

    row1, row2, row3 = (
        RowHandler()
        .force_create_rows(
            user,
            table,
            [
                {field.db_column: "Row 1"},
                {field.db_column: "Row 2"},
                {field.db_column: "Row 3"},
            ],
        )
        .created_rows
    )

    # (Fake) search updates to delete
    PendingSearchValueUpdate.objects.bulk_create(
        [
            PendingSearchValueUpdate(
                field_id=field.id, row_id=row1.id, deletion_workspace_id=workspace.id
            ),
            PendingSearchValueUpdate(
                field_id=field.id, row_id=row2.id, deletion_workspace_id=workspace.id
            ),
            PendingSearchValueUpdate(
                field_id=field.id, row_id=row3.id, deletion_workspace_id=workspace.id
            ),
        ]
    )

    workspace_search_table = SearchHandler.get_workspace_search_table_model(
        workspace.id
    )
    assert workspace_search_table.objects.count() == 3
    assert PendingSearchValueUpdate.objects_and_trash.count() == 3

    periodic_check_pending_search_data()

    # After processing, the search table should be empty and pending updates marked for
    # deletion should be deleted
    assert workspace_search_table.objects.count() == 0
    assert PendingSearchValueUpdate.objects_and_trash.count() == 0

    # Too-old pending updates should be deleted, without creating a search value
    with freeze_time("2024-01-01 00:00:00"):
        PendingSearchValueUpdate.objects.create(field_id=field.id, row_id=1)

    assert PendingSearchValueUpdate.objects_and_trash.count() == 1
    assert workspace_search_table.objects.count() == 0

    periodic_check_pending_search_data()

    # The pending update is removed and nothing is created in the search table
    assert PendingSearchValueUpdate.objects_and_trash.count() == 0
    assert workspace_search_table.objects.count() == 0

    # If there are valid pending updates for a table, it should re-schedule the task
    # and add them
    PendingSearchValueUpdate.objects.create(field_id=field.id, row_id=1)
    assert PendingSearchValueUpdate.objects_and_trash.count() == 1
    assert workspace_search_table.objects.count() == 0

    periodic_check_pending_search_data()

    # The task is called for the table with pending updates and the search value
    # is created accordingly
    assert PendingSearchValueUpdate.objects_and_trash.count() == 0
    assert workspace_search_table.objects.count() == 1
