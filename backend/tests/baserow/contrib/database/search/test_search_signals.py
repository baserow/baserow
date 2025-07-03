from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError

from baserow.contrib.database.search.signals import view_loaded_maybe_create_tsvector


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.table.tasks"
    ".setup_new_background_update_and_search_columns.delay"
)
def test_view_loaded_maybe_create_tsvector_does_not_raise_if_redis_down(
    mock_setup,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    table = data_fixture.create_database_table(
        needs_background_update_column_added=False
    )
    mock_setup.si.side_effect = ConnectionError("connection error")
    with django_capture_on_commit_callbacks(execute=True):
        view_loaded_maybe_create_tsvector(None, table, table.get_model())


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.table.tasks"
    ".setup_new_background_update_and_search_columns.delay"
)
def test_view_loaded_doesnt_run_for_existing_table_with_cols_already(
    mock_setup,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    table = data_fixture.create_database_table(
        needs_background_update_column_added=True
    )
    with django_capture_on_commit_callbacks(execute=True):
        view_loaded_maybe_create_tsvector(None, table, table.get_model())
    assert not mock_setup.called


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.table.tasks"
    ".setup_new_background_update_and_search_columns.delay"
)
def test_view_loaded_doesnt_run_for_existing_table_when_fts_disabled(
    mock_setup,
    data_fixture,
    django_capture_on_commit_callbacks,
    disable_full_text_search,
):
    table = data_fixture.create_database_table(
        needs_background_update_column_added=False
    )
    data_fixture.create_text_field(
        tsvector_column_created=False,
        table=table,
    )
    with django_capture_on_commit_callbacks(execute=True):
        view_loaded_maybe_create_tsvector(None, table, table.get_model())
    assert not mock_setup.called
