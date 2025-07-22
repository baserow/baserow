from unittest.mock import patch

from django.db import connection

import pytest

from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search.receivers import view_loaded
from baserow.contrib.database.trash.models import TrashedRows
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_perm_deleted_workspace(data_fixture):
    """
    Search table is removed when a workspace is permanently deleted.
    """

    initial_tables = connection.introspection.table_names()

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    # This creates the user table and the workspace search table.
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    text_field = data_fixture.create_text_field(table=table_1)
    row_1 = table_1.get_model().objects.create(**{text_field.db_column: "Test row"})

    tables = connection.introspection.table_names()

    # The search table now exists
    assert set(tables) - set(initial_tables) == {
        table_1.get_model()._meta.db_table,
        SearchHandler.get_workspace_search_table_name(workspace.id),
    }

    TrashHandler.trash(user, workspace, None, workspace)
    TrashHandler.permanently_delete(workspace)

    final_tables = connection.introspection.table_names()
    # The search table is removed, together with the user table.
    assert set(final_tables) == set(initial_tables)


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.mark_search_data_for_deletion"
)
def test_perm_deleted_database(mock, data_fixture):
    """
    Test that the search data is cleaned up when a database is permanently deleted.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database, name="table_1", order=1)
    data_fixture.create_database_table(database=database, name="table_2", order=2)

    TrashHandler.trash(user, workspace, database, database)
    TrashHandler.permanently_delete(database)

    assert mock.call_count == 2
    assert mock.call_args_list[0][0][0].name == "table_1"
    assert mock.call_args_list[0][1] == {}  # All fields and rows

    assert mock.call_args_list[1][0][0].name == "table_2"
    assert mock.call_args_list[1][1] == {}  # All fields and rows


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.mark_search_data_for_deletion"
)
def test_perm_deleted_table(mock, data_fixture):
    """
    Test that the search data is cleaned up when a table is permanently deleted.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    table_2 = data_fixture.create_database_table(database=database, name="table_2")

    TrashHandler.trash(user, workspace, database, table_1)
    TrashHandler.permanently_delete(table_1)

    assert mock.call_count == 1
    assert mock.call_args_list[0][0][0].name == "table_1"
    assert mock.call_args_list[0][1] == {}  # All fields and rows


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.mark_search_data_for_deletion"
)
def test_perm_deleted_field(mock, data_fixture):
    """
    Test that the search data is cleaned up when a table is permanently deleted.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    text_field = data_fixture.create_text_field(table=table_1)
    text_field_id = text_field.id

    TrashHandler.trash(user, workspace, database, text_field)
    TrashHandler.permanently_delete(text_field)

    assert mock.call_count == 1
    assert mock.call_args_list[0][0][0].id == table_1.id
    # All rows for this field
    assert mock.call_args_list[0][1] == {"field_ids": [text_field_id]}


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.mark_search_data_for_deletion"
)
def test_perm_deleted_row(mock, data_fixture):
    """
    Test that the search data is cleaned up when a row is permanently deleted.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    text_field = data_fixture.create_text_field(table=table_1)
    row_1 = table_1.get_model().objects.create(**{text_field.db_column: "Test row"})
    row_1_id = row_1.id

    TrashHandler.trash(user, workspace, database, row_1)
    TrashHandler.permanently_delete(row_1, parent_id=table_1.id)

    assert mock.call_count == 1
    assert mock.call_args_list[0][0][0].id == table_1.id
    # All fields for this row
    assert mock.call_args_list[0][1] == {"row_ids": [row_1_id]}


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.mark_search_data_for_deletion"
)
def test_perm_deleted_rows(mock, data_fixture):
    """
    Test that the search data is cleaned up when rows are permanently deleted.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    text_field = data_fixture.create_text_field(table=table_1)

    row_1 = table_1.get_model().objects.create(**{text_field.db_column: "Test row 1"})
    row_2 = table_1.get_model().objects.create(**{text_field.db_column: "Test row 2"})
    row_1_id = row_1.id
    row_2_id = row_2.id

    trashed_rows = TrashedRows.objects.create(
        row_ids=[row_1_id, row_2_id], table=table_1
    )
    TrashHandler.trash(user, workspace, database, trashed_rows)
    TrashHandler.permanently_delete(trashed_rows, parent_id=table_1.id)

    assert mock.call_count == 1
    assert mock.call_args_list[0][0][0].id == table_1.id
    # All fields for these rows
    assert mock.call_args_list[0][1] == {"row_ids": [row_1_id, row_2_id]}


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.search.handler.SearchHandler.schedule_update_search_data"
)
def test_schedule_update_search_data_is_triggered_on_first_view_load(
    mock, data_fixture
):
    """
    Test that the search data update is scheduled when a view is loaded for the first
    time if there are uninitialized search data for the table.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database, name="table_1")
    text_field = data_fixture.create_text_field(table=table_1)

    row_1 = table_1.get_model().objects.create(**{text_field.db_column: "Test row 1"})
    grid_view = data_fixture.create_grid_view(
        user=user, table=table_1, name="Grid view"
    )

    assert mock.call_count == 0
    view_loaded.send(
        sender=grid_view, view=grid_view, table=table_1, table_model=table_1.get_model()
    )
    assert mock.call_count == 1
    assert mock.call_args_list[0][0][0].id == table_1.id
