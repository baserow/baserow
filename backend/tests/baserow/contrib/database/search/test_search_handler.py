from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.db import ProgrammingError, transaction

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler, SearchMode
from baserow.contrib.database.search.models import PendingSearchValueUpdate


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
    model = table.get_model()
    assert list(model.get_fields_with_uninitialized_search_data()) == [text_field]

    SearchHandler.initialize_missing_search_data(table)

    assert list(model.get_fields_with_uninitialized_search_data()) == []


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


@pytest.mark.django_db
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
    assert search_table.objects.count() == 0
    SearchHandler.update_search_data(table)

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
    SearchHandler.delete_search_data(
        table, field_ids=[text_field.id], row_ids=[row1.id]
    )
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 5
    assert res == [
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row2.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]

    # All fields for a specific row
    SearchHandler.delete_search_data(table, row_ids=[row2.id])
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 3
    assert res == [
        {"field_id": text_field.id, "row_id": row3.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]

    # All rows for a specific field
    SearchHandler.delete_search_data(table, field_ids=[number_field.id])
    res = list(search_table.objects.values("field_id", "row_id"))
    assert len(res) == 1
    assert res == [{"field_id": text_field.id, "row_id": row3.id}]

    # All table search data
    SearchHandler.delete_search_data(table)
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
                {text_field.db_column: "Row 1", number_field.db_column: 1},
                {text_field.db_column: "Row 2"},
                {number_field.db_column: 3},
            ],
            model=model,
        )
        .created_rows
    )

    SearchHandler.initialize_missing_search_data(table)
    assert list(model.get_fields_with_uninitialized_search_data()) == []

    search_table = SearchHandler.get_workspace_search_table_model(
        table.database.workspace_id
    )
    res = list(search_table.objects.values("field_id", "row_id"))
    # Emtpy values are not stored during initialization.
    assert len(res) == 4
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id},
        {"field_id": text_field.id, "row_id": row2.id},
        {"field_id": number_field.id, "row_id": row1.id},
        {"field_id": number_field.id, "row_id": row3.id},
    ]


@pytest.mark.django_db(transaction=True)
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.process_search_data_updates"
)
def test_update_rows_create_update_entries_for_all_updated_fields(mock, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'a'")
    model = table.get_model()

    SearchHandler.initialize_missing_search_data(table)
    assert PendingSearchValueUpdate.objects.count() == 0

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

    res = list(PendingSearchValueUpdate.objects.values("field_id", "row_id"))
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

    SearchHandler.initialize_missing_search_data(table)

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
    SearchHandler.initialize_missing_search_data(table)
    assert search_table.objects.count() == 0

    dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    with freeze_time(dt):
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

    # After the initialization, the search data is created for all fields
    # no matter if the value is empty or not.
    res = list(search_table.objects.values("field_id", "row_id", "updated_on"))
    assert len(res) == 6
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id, "updated_on": dt},
        {"field_id": text_field.id, "row_id": row2.id, "updated_on": dt},
        {"field_id": text_field.id, "row_id": row3.id, "updated_on": dt},
        {"field_id": number_field.id, "row_id": row1.id, "updated_on": dt},
        {"field_id": number_field.id, "row_id": row2.id, "updated_on": dt},
        {"field_id": number_field.id, "row_id": row3.id, "updated_on": dt},
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
                {"id": row2.id, text_field.db_column: "", number_field.db_column: 5},
                {
                    "id": row3.id,
                    text_field.db_column: "Row 3",
                    number_field.db_column: 6,
                },
            ],
            model=model,
        )

    res = list(search_table.objects.values("field_id", "row_id", "updated_on"))
    assert len(res) == 6
    assert res == [
        {"field_id": text_field.id, "row_id": row1.id, "updated_on": dt2},
        {"field_id": text_field.id, "row_id": row2.id, "updated_on": dt2},
        {"field_id": text_field.id, "row_id": row3.id, "updated_on": dt2},
        {"field_id": number_field.id, "row_id": row1.id, "updated_on": dt2},
        {"field_id": number_field.id, "row_id": row2.id, "updated_on": dt2},
        {"field_id": number_field.id, "row_id": row3.id, "updated_on": dt2},
    ]
