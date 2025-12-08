from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.db import ProgrammingError, transaction

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler, SearchMode
from baserow.contrib.database.search.models import PendingSearchValueUpdate
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)


def test_escape_query():
    # Spacing is standardized.
    assert SearchHandler.escape_query("Full   text   search") == "Full text search"
    # Escape colons for URLs.
    assert SearchHandler.escape_query("https://baserow.io") == "https baserow io"
    # Special characters are trimmed.
    assert SearchHandler.escape_query("Base<&(|)!>row") == "Base row"
    # Leading or trailing spaces trimmed.
    assert SearchHandler.escape_query("  Full text search  ") == "Full text search"


@pytest.mark.django_db
def test_get_default_search_mode_for_table_with_workspace_search_data(data_fixture):
    table = data_fixture.create_database_table()

    assert (
        SearchHandler.get_default_search_mode_for_table(table)
        == SearchMode.FT_WITH_COUNT
    )


@pytest.mark.django_db
def test_get_default_search_mode_for_table_with_tsvectors_for_templates():
    mock_table = Mock()
    mock_table.database = Mock()

    mock_table.database.workspace = Mock()
    mock_table.database.workspace.has_template = lambda: True

    assert (
        SearchHandler.get_default_search_mode_for_table(mock_table) == SearchMode.COMPAT
    )


def test_escape_postgres_query_with_per_token_wildcard():
    # Doesn't attempt to match the current search
    assert (
        SearchHandler.escape_postgres_query("french cuisi", True)
        == "$$french$$:* <-> $$cuisi$$:*"
    )


def test_escape_postgres_query_without_per_token_wildcard():
    # Attempts to match the current search as closely as possible
    assert (
        SearchHandler.escape_postgres_query("french cuisi", False)
        == "$$french$$ <-> $$cuisi$$:*"
    )


@pytest.mark.django_db
def test_get_fields_missing_search_index(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)
    model = table.get_model()
    assert list(model.get_fields_with_uninitialized_search_data()) == []
    text_field = data_fixture.create_text_field(table=table)

    def get_uninitialized_fields():
        return list(table.get_model().get_fields_with_uninitialized_search_data())

    assert get_uninitialized_fields() == [text_field]
    assert PendingSearchValueUpdate.objects.count() == 0

    SearchHandler.initialize_missing_search_data(table)

    assert get_uninitialized_fields() == []
    assert list(PendingSearchValueUpdate.objects.values("field_id", "row_id")) == [
        {"field_id": text_field.id, "row_id": None}
    ]


@pytest.mark.django_db
def test_create_workspace_search_table(data_fixture):
    workspace = data_fixture.create_workspace()
    assert not SearchHandler.workspace_search_table_exists(workspace.id)

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)

    assert SearchHandler.workspace_search_table_exists(workspace.id)

    search_table = SearchHandler.get_workspace_search_table_model(workspace.id)
    assert search_table.objects.count() == 0


@pytest.mark.django_db
def test_delete_workspace_search_table(data_fixture):
    workspace = data_fixture.create_workspace()
    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)

    assert SearchHandler.workspace_search_table_exists(workspace.id)
    search_table = SearchHandler.get_workspace_search_table_model(workspace.id)
    assert search_table.objects.count() == 0

    SearchHandler.delete_workspace_search_table_if_exists(workspace.id)

    assert not SearchHandler.workspace_search_table_exists(workspace.id)
    with pytest.raises(ProgrammingError):
        search_table.objects.count()


@pytest.mark.django_db(transaction=True)
def test_delete_search_data(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    model = table.get_model()

    row1, row2, row3 = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {text_field.db_column: "Row 1", number_field.db_column: 1},
                {text_field.db_column: "Row 2", number_field.db_column: 2},
                {text_field.db_column: "Row 3", number_field.db_column: 3},
            ],
            model=model,
        )
        .created_rows
    )

    search_table = SearchHandler.get_workspace_search_table_model(
        table.database.workspace_id
    )

    def get_marked_for_deletion():
        return PendingSearchValueUpdate.objects_and_trash.filter(
            deletion_workspace_id__isnull=False
        )

    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 6
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id},
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row2.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]

    # A specific cell
    SearchHandler.mark_search_data_for_deletion(
        table, field_ids=[text_field.id], row_ids=[row1.id]
    )
    assert get_marked_for_deletion().count() == 1
    SearchHandler.process_search_data_marked_for_deletion()
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 5
    assert res == [
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row2.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]
    assert get_marked_for_deletion().count() == 0

    # All fields for a specific row
    SearchHandler.mark_search_data_for_deletion(
        table, field_ids=[text_field.id, number_field.id], row_ids=[row2.id]
    )
    assert get_marked_for_deletion().count() == 2
    SearchHandler.process_search_data_marked_for_deletion()
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 3
    assert res == [
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]
    assert get_marked_for_deletion().count() == 0

    # All rows for a specific field
    SearchHandler.mark_search_data_for_deletion(table, field_ids=[number_field.id])
    assert get_marked_for_deletion().count() == 1
    SearchHandler.process_search_data_marked_for_deletion()
    assert get_marked_for_deletion().count() == 0
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 1
    assert res == [{"field_id": text_field.id, "row_id": row3.id}]

    # All table search data
    SearchHandler.mark_search_data_for_deletion(table, field_ids=[text_field.id])
    assert get_marked_for_deletion().count() == 1
    SearchHandler.process_search_data_marked_for_deletion()
    assert get_marked_for_deletion().count() == 0
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 0


@pytest.mark.django_db
def test_initialize_missing_search_data(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    model = table.get_model()

    assert list(model.get_fields_with_uninitialized_search_data()) == [
        text_field,
        number_field,
    ]

    row1, row2, row3 = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {text_field.db_column: "a", number_field.db_column: 1},
                {text_field.db_column: "b"},
                {number_field.db_column: 3},
            ],
            model=model,
        )
        .created_rows
    )

    SearchHandler.initialize_missing_search_data(table)
    model = table.get_model()  # refetch fields attributes
    assert list(model.get_fields_with_uninitialized_search_data()) == []

    SearchHandler.process_search_data_updates(table)
    search_table = SearchHandler.get_workspace_search_table_model(
        table.database.workspace_id
    )
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 6
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id},
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row2.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]


@pytest.mark.django_db(transaction=True)
def test_update_rows_create_update_entries_for_all_updated_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'a'")
    model = table.get_model()

    SearchHandler.initialize_missing_search_data(table)
    assert PendingSearchValueUpdate.objects.count() == 2
    SearchHandler.process_search_data_updates(table)
    assert PendingSearchValueUpdate.objects.count() == 0

    with patch(
        "baserow.contrib.database.search.handler.SearchHandler.process_search_data_updates"
    ) as mock:
        row1, row2, row3 = (
            RowHandler()
            .force_create_rows(
                user=user,
                table=table,
                rows_values=[
                    {text_field.db_column: "Row 1"},
                    {text_field.db_column: "Row 2"},
                    {},
                ],
                model=model,
            )
            .created_rows
        )
        assert (
            mock.call_count == 2
        )  # one for the text field, and one for the formula field

    res = list(
        PendingSearchValueUpdate.objects.order_by("field_id", "row_id").values(
            "field_id", "row_id"
        )
    )
    assert len(res) == 6
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id},
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": formula_field.id, "row_id": row1.id},
        {"field_id": formula_field.id, "row_id": row2.id},
        {"field_id": formula_field.id, "row_id": row3.id},
    ]


@pytest.mark.django_db()
@patch("baserow.contrib.database.search.handler.SearchHandler.update_search_data")
def test_update_rows_process_update_entries(mock, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'b'")

    PendingSearchValueUpdate.objects.bulk_create(
        [
            PendingSearchValueUpdate(
                table_id=table.id, field_id=text_field.id, row_id=1
            ),
            PendingSearchValueUpdate(
                table_id=table.id, field_id=text_field.id, row_id=2
            ),
            PendingSearchValueUpdate(
                table_id=table.id, field_id=formula_field.id, row_id=1
            ),
            PendingSearchValueUpdate(
                table_id=table.id, field_id=formula_field.id, row_id=2
            ),
        ]
    )

    mock.reset_mock()
    SearchHandler.process_search_data_updates(table)
    assert mock.call_count == 1
    assert mock.call_args[0][0] == table
    assert mock.call_args[1] == {
        "field_ids": unordered([text_field.id, formula_field.id]),
        "row_ids": unordered([1, 2]),
    }

    PendingSearchValueUpdate.objects.count() == 0

    # If there's an update for all the rows (row_id=None), all other individual
    # updates are ignored.
    PendingSearchValueUpdate.objects.bulk_create(
        [
            PendingSearchValueUpdate(table_id=table.id, field_id=text_field.id),
            PendingSearchValueUpdate(
                table_id=table.id, field_id=text_field.id, row_id=2
            ),
            PendingSearchValueUpdate(
                table_id=table.id, field_id=text_field.id, row_id=3
            ),
        ]
    )

    mock.reset_mock()
    SearchHandler.process_search_data_updates(table)
    assert mock.call_count == 1
    assert mock.call_args[0][0] == table
    assert mock.call_args[1] == {"field_ids": [text_field.id]}
    PendingSearchValueUpdate.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_update_search_data(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    model = table.get_model()

    search_table = SearchHandler.get_workspace_search_table_model(
        workspace_id=table.database.workspace_id
    )
    SearchHandler.update_search_data(table)
    assert search_table.objects.count() == 0

    dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    with freeze_time(dt1):
        row1, row2, row3 = (
            RowHandler()
            .force_create_rows(
                user=user,
                table=table,
                rows_values=[
                    {text_field.db_column: "Row 1", number_field.db_column: 1},
                    {text_field.db_column: "Row 2"},
                    {},
                ],
                model=model,
            )
            .created_rows
        )

    def get_search_data():
        return list(
            search_table.objects.order_by("row_id", "field_id").values(
                "field_id", "row_id", "updated_on"
            )
        )

    # After the initialization, the search data is created for all fields
    res = get_search_data()
    assert len(res) == 6
    assert res == [
        {"row_id": row1.id, "field_id": text_field.id, "updated_on": dt1},
        {"row_id": row1.id, "field_id": number_field.id, "updated_on": dt1},
        {"row_id": row2.id, "field_id": text_field.id, "updated_on": dt1},
        {"row_id": row2.id, "field_id": number_field.id, "updated_on": dt1},
        {"row_id": row3.id, "field_id": text_field.id, "updated_on": dt1},
        {"row_id": row3.id, "field_id": number_field.id, "updated_on": dt1},
    ]

    dt2 = datetime(2025, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
    with freeze_time(dt2), transaction.atomic():
        # If the rows are updated, the existing search data is updated
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {
                    "id": row1.id,
                    text_field.db_column: None,
                    number_field.db_column: None,
                },
                {
                    "id": row2.id,
                    text_field.db_column: "",
                    number_field.db_column: 5,
                },
            ],
            model=model,
        )

    res = get_search_data()
    assert len(res) == 6
    assert res == [
        {"row_id": row1.id, "field_id": text_field.id, "updated_on": dt2},
        {"row_id": row1.id, "field_id": number_field.id, "updated_on": dt2},
        {"row_id": row2.id, "field_id": text_field.id, "updated_on": dt2},
        {"row_id": row2.id, "field_id": number_field.id, "updated_on": dt2},
        # Unmodified row3 still has the original timestamp
        {"row_id": row3.id, "field_id": text_field.id, "updated_on": dt1},
        {"row_id": row3.id, "field_id": number_field.id, "updated_on": dt1},
    ]

    RowHandler().delete_row(user=user, table=table, row=row1, model=model)

    # Trashing rows doesn't delete the search data
    res = get_search_data()
    assert len(res) == 6

    # Once the row is permanently deleted, the search data is removed
    TrashHandler.permanently_delete(row1, table.id)

    def get_marked_for_deletion():
        return PendingSearchValueUpdate.objects_and_trash.filter(
            deletion_workspace_id__isnull=False
        )

    assert get_marked_for_deletion().count() == 2  # both fields for row1
    SearchHandler.process_search_data_marked_for_deletion()
    assert get_marked_for_deletion().count() == 0
    res = get_search_data()

    assert len(res) == 4
    assert res == [
        {"row_id": row2.id, "field_id": text_field.id, "updated_on": dt2},
        {"row_id": row2.id, "field_id": number_field.id, "updated_on": dt2},
        {"row_id": row3.id, "field_id": text_field.id, "updated_on": dt1},
        {"row_id": row3.id, "field_id": number_field.id, "updated_on": dt1},
    ]

    # Trashing a field doesn't delete the search data
    FieldHandler().delete_field(user=user, field=number_field)

    res = get_search_data()
    assert len(res) == 4

    # Once the field is permanently deleted, the search data is removed
    with transaction.atomic():
        TrashHandler.permanently_delete(number_field)

    assert get_marked_for_deletion().count() == 1  # all rows for the number field
    SearchHandler.process_search_data_marked_for_deletion()
    assert get_marked_for_deletion().count() == 0

    res = get_search_data()
    assert len(res) == 2
    assert res == [
        {"row_id": row2.id, "field_id": text_field.id, "updated_on": dt2},
        {"row_id": row3.id, "field_id": text_field.id, "updated_on": dt1},
    ]

    # Trashing a table doesn't delete the search data
    TableHandler().delete_table(user=user, table=table)
    res = get_search_data()
    assert len(res) == 2

    # Once the table is permanently deleted, the search data is removed
    with transaction.atomic():
        TrashHandler.permanently_delete(table)

    assert get_marked_for_deletion().count() == 1  # all rows for the text field
    SearchHandler.process_search_data_marked_for_deletion()
    assert get_marked_for_deletion().count() == 0
    res = get_search_data()
    assert len(res) == 0


@pytest.mark.django_db(transaction=True)
def test_creating_a_snapshot_doesnt_schedule_search_updates(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)

    RowHandler().force_create_rows(
        user=user,
        table=table,
        rows_values=[
            {text_field.db_column: "Row 1", number_field.db_column: 1},
            {text_field.db_column: "Row 2"},
            {},
        ],
    )

    with patch(
        "baserow.contrib.database.search.handler.SearchHandler.schedule_update_search_data"
    ) as mock:
        handler = SnapshotHandler()
        snapshot = handler.create(table.database_id, user, "Test snapshot")
        handler.perform_create(snapshot, Progress(100))
        assert mock.call_count == 0

        # once the snapshot is restored, the search data is updated
        restored_app = handler.perform_restore(snapshot, Progress(100))
        new_table = restored_app.table_set.first()
        assert mock.call_count == 1
        assert mock.call_args[0][0] == new_table
        assert mock.call_args[1] == {}  # the whole table


@pytest.mark.django_db
def test_not_schedule_task_if_workspace_is_none(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, workspace=None)
    table = data_fixture.create_database_table(user=user, database=database)

    with patch(
        "baserow.contrib.database.search.handler.SearchHandler.update_search_data"
    ) as mock:
        SearchHandler.schedule_update_search_data(table)

        assert mock.call_count == 0
        assert PendingSearchValueUpdate.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.search.tasks.update_search_data.apply_async")
def test_search_data_updates_dont_clear_concurrent_updates(mock, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    with freeze_time("2025-01-01 12:00:05"):
        SearchHandler.initialize_missing_search_data(table)
        SearchHandler.process_search_data_updates(table)

        RowHandler().force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {text_field.db_column: "Row 1"},
                {text_field.db_column: "Row 2"},
            ],
        )

    # This simulates an update taks that was already running when the
    # `process_search_data_updates` was called. The `updated_on` timestamp is not
    # checked when fetching the pending updates, but it is used to determine which
    # updates are older and should be deleted.

    assert PendingSearchValueUpdate.objects.count() == 2
    with freeze_time("2025-01-01 12:00:00"):
        SearchHandler.process_search_data_updates(table)

        # The updates for the new rows have not been cleared, because they have a newer
        # `updated_on` timestamp compared to when the `process_search_data_updates` was
        # called.
        assert PendingSearchValueUpdate.objects.count() == 2

    with freeze_time("2025-01-01 12:00:10"):
        # If the updates are processed again, the pending updates are cleared.
        SearchHandler.process_search_data_updates(table)
        assert PendingSearchValueUpdate.objects.count() == 0
