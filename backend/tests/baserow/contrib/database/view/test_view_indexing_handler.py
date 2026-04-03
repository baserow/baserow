from unittest.mock import patch

from django.db import OperationalError

import pytest

from baserow.contrib.database.views.handler import ViewHandler, ViewIndexingHandler
from baserow.contrib.database.views.models import (
    OWNERSHIP_TYPE_COLLABORATIVE,
)


@pytest.mark.django_db(transaction=True)
def test_update_index_long_text_over_max_size_doesnt_fail(data_fixture):
    """
    Sort expressions use Left() to truncate text columns, so the index should
    be successfully created even when row values exceed PostgreSQL's btree
    index maximum entry size (~2712 bytes).
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()

    import base64
    import os

    large_text_value = base64.b64encode(os.urandom(8000)).decode("ascii")

    # Insert a row with a text value large enough that it would exceed
    # PostgreSQL's btree index maximum entry size without Left() truncation.
    table_model.objects.create(**{f"field_{long_text_field.id}": large_text_value})

    handler.create_sort(user=user, view=grid_view, field=long_text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    # The index should be created successfully because Left() truncation keeps
    # the indexed values within btree's size limit.
    assert ViewIndexingHandler.does_index_exist(index.name) is True


@pytest.mark.django_db(transaction=True)
def test_update_index_multiple_fields_over_max_size_doesnt_fail(
    data_fixture,
):
    """
    Same as above but with two long text fields combined. Left() truncation
    should keep the total index entry size within limits.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    long_text_field = data_fixture.create_long_text_field(user=user, table=table)
    long_text_field_2 = data_fixture.create_long_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()

    import base64
    import os

    large_text_value = base64.b64encode(os.urandom(4000)).decode("ascii")

    # Insert a row with text values that combined would exceed PostgreSQL's btree
    # index maximum entry size without Left() truncation.
    table_model.objects.create(
        **{
            f"field_{long_text_field.id}": large_text_value,
            f"field_{long_text_field_2.id}": large_text_value,
        }
    )

    handler.create_sort(user=user, view=grid_view, field=long_text_field, order="ASC")
    handler.create_sort(user=user, view=grid_view, field=long_text_field_2, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    # The index should be created successfully because Left() truncation keeps
    # the indexed values within btree's size limit.
    assert ViewIndexingHandler.does_index_exist(index.name) is True


@pytest.mark.django_db(transaction=True)
def test_update_index_catches_operational_error_gracefully(data_fixture):
    """
    If PostgreSQL raises an OperationalError during index creation (e.g., due
    to an unforeseen size issue), the error is caught and the view's
    db_index_name is set to None instead of crashing.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")

    # Mock the schema editor's add_index to simulate a btree size error.
    with patch(
        "baserow.contrib.database.views.handler.safe_django_schema_editor"
    ) as mock_editor_ctx:
        mock_schema_editor = mock_editor_ctx.return_value.__enter__.return_value
        mock_schema_editor.add_index.side_effect = OperationalError(
            "index row size 6568 exceeds btree version 4 maximum 2704 for index"
        )

        ViewIndexingHandler.update_index(grid_view, table_model)

    grid_view.refresh_from_db()
    # The index creation failed, so db_index_name should be None.
    assert grid_view.db_index_name is None


@pytest.mark.django_db(transaction=True)
def test_drop_all_indexes_for_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    grid_view_2 = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")
    handler.create_sort(user=user, view=grid_view_2, field=text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)
    ViewIndexingHandler.update_index(grid_view_2, table_model)
    grid_view.refresh_from_db()
    grid_view_2.refresh_from_db()
    assert grid_view.db_index_name is not None
    assert grid_view_2.db_index_name is not None

    index = ViewIndexingHandler.get_index(grid_view, table_model)
    assert ViewIndexingHandler.does_index_exist(index.name) is True

    index2 = ViewIndexingHandler.get_index(grid_view_2, table_model)
    assert ViewIndexingHandler.does_index_exist(index2.name) is True

    ViewIndexingHandler.drop_all_indexes_for_table(table.id)

    grid_view.refresh_from_db()
    assert grid_view.db_index_name is None
    assert ViewIndexingHandler.does_index_exist(index.name) is False
    grid_view_2.refresh_from_db()
    assert grid_view_2.db_index_name is None
    assert ViewIndexingHandler.does_index_exist(index2.name) is False


@pytest.mark.django_db(transaction=True)
def test_handle_index_row_size_error_drops_indexes(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user=user, table=table)
    handler = ViewHandler()
    grid_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    table_model = table.get_model()
    handler.create_sort(user=user, view=grid_view, field=text_field, order="ASC")

    ViewIndexingHandler.update_index(grid_view, table_model)
    grid_view.refresh_from_db()
    assert grid_view.db_index_name is not None

    ViewIndexingHandler.handle_index_row_size_error(table.id)

    grid_view.refresh_from_db()
    assert grid_view.db_index_name is None
