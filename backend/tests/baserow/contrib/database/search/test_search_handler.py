from unittest.mock import Mock, patch

from django.db import connection
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.search.handler import SearchHandler, SearchModes
from baserow.core.trash.handler import TrashHandler


def test_escape_query():
    # Spacing is standardized.
    assert SearchHandler.escape_query("Full   text   search") == "Full text search"
    # Escape colons for URLs.
    assert SearchHandler.escape_query("https://baserow.io") == "https baserow io"
    # Special characters are trimmed.
    assert SearchHandler.escape_query("Base<&(|)!>row") == "Base row"
    # Leading or trailing spaces trimmed.
    assert SearchHandler.escape_query("  Full text search  ") == "Full text search"


def test_get_default_search_mode_for_table_with_tsvectors_supported():
    mock_table = Mock(tsvectors_are_supported=True)
    mock_table.database = Mock()

    mock_table.database.workspace = Mock()
    mock_table.database.workspace.has_template = lambda: False

    assert (
        SearchHandler.get_default_search_mode_for_table(mock_table)
        == SearchModes.MODE_FT_WITH_COUNT
    )


def test_get_default_search_mode_for_table_with_tsvectors_for_templates():
    mock_table = Mock(tsvectors_are_supported=True)
    mock_table.database = Mock()

    mock_table.database.workspace = Mock()
    mock_table.database.workspace.has_template = lambda: True

    assert (
        SearchHandler.get_default_search_mode_for_table(mock_table)
        == SearchModes.MODE_COMPAT
    )


def test_get_default_search_mode_for_table_with_tsvectors_unsupported():
    mock_table = Mock(tsvectors_are_supported=False)
    assert (
        SearchHandler.get_default_search_mode_for_table(mock_table)
        == SearchModes.MODE_COMPAT
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


@pytest.mark.django_db()
def test_create_tsvector_columns(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(
        user,
        force_add_tsvectors=False,
    )
    data_fixture.create_text_field(
        table=table,
        tsvector_column_created=False,
    )

    for field in table.field_set.all():
        assert not field.tsvector_column_created

    table = SearchHandler.sync_tsvector_columns(table)
    for field in table.field_set.all():
        assert field.tsvector_column_created

    model = table.get_model()
    for field in model.get_searchable_fields():
        model._meta.get_field(field.tsv_db_column)


@pytest.mark.django_db
def test_get_fields_missing_search_index(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)
    model = table.get_model()
    assert list(model.get_fields_missing_search_index()) == []
    text_field = data_fixture.create_text_field(
        table=table, tsvector_column_created=False
    )
    model = table.get_model()
    assert list(model.get_fields_missing_search_index()) == [text_field]


@pytest.mark.django_db
def test_updating_link_row_field_so_it_moves_between_tables_syncs_properly(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    table_c = data_fixture.create_database_table(user, database=database)
    data_fixture.create_text_field(user, table=table_c, primary=True)

    assert link_field.tsv_db_column in get_column_names(table_a)
    assert link_field.link_row_related_field.tsv_db_column in get_column_names(table_b)
    assert link_field.link_row_related_field.tsv_db_column not in get_column_names(
        table_c
    )

    link_field = FieldHandler().update_field(user, link_field, link_row_table=table_c)

    # The update should work for all involved tables
    SearchHandler().update_tsvector_columns(table_c, False)
    SearchHandler().update_tsvector_columns(table_b, False)
    SearchHandler().update_tsvector_columns(table_a, False)

    assert link_field.tsv_db_column in get_column_names(table_a)
    assert link_field.link_row_related_field.tsv_db_column not in get_column_names(
        table_b
    )
    assert link_field.link_row_related_field.tsv_db_column in get_column_names(table_c)


def get_column_names(tbl):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            [tbl.get_database_table_name()],
        )
        return [r[0] for r in cursor.fetchall()]


@pytest.mark.django_db
def test_updating_link_row_field_so_it_no_longer_has_related_field_syncs_tsvs(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )

    related_tsv_column_name = link_field.link_row_related_field.tsv_db_column
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name in get_column_names(table_b)

    FieldHandler().update_field(user, link_field, has_related_field=False)

    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name not in get_column_names(table_b)

    FieldHandler().update_field(user, link_field, has_related_field=True)

    link_field.refresh_from_db()
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert link_field.link_row_related_field.tsv_db_column in get_column_names(table_b)


@pytest.mark.django_db
def test_updating_link_row_field_so_it_points_at_itself_and_back_syncs_tsvs(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )

    related_tsv_column_name = link_field.link_row_related_field.tsv_db_column
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name in get_column_names(table_b)

    FieldHandler().update_field(user, link_field, link_row_table=table_a)

    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name not in get_column_names(table_b)

    # has_related_field is False because its always false for self ref link fields atm.
    FieldHandler().update_field(user, link_field, link_row_table=table_b)

    link_field.refresh_from_db()
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name not in get_column_names(table_b)


@pytest.mark.django_db
def test_updating_link_row_field_so_it_points_at_itself_and_back_with_related_syncs_tsvs(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )

    related_tsv_column_name = link_field.link_row_related_field.tsv_db_column
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name in get_column_names(table_b)

    FieldHandler().update_field(user, link_field, link_row_table=table_a)

    assert link_field.tsv_db_column in get_column_names(table_a)
    assert related_tsv_column_name not in get_column_names(table_b)

    FieldHandler().update_field(
        user, link_field, link_row_table=table_b, has_related_field=True
    )

    link_field.refresh_from_db()
    assert link_field.tsv_db_column in get_column_names(table_a)
    assert link_field.link_row_related_field.tsv_db_column in get_column_names(table_b)


@pytest.mark.django_db
def test_querying_table_with_trashed_field_doesnt_include_its_tsv(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    rows_in_a = data_fixture.create_rows_in_table(table_a, [[]])
    rows_in_b = data_fixture.create_rows_in_table(table_b, [[]], [])
    m2m = getattr(rows_in_a[0], link_field.db_column)
    m2m.set([rows_in_b[0].id])

    assert len(list(table_a.get_model().objects.all())) == 1
    assert len(m2m.all()) == 1

    TrashHandler.trash(user, database.workspace, database, link_field)
    # Force delete the tsv so if it gets queryed by the SQL it crashes the test
    SearchHandler.after_field_perm_delete(link_field)

    requeried_rows_from_a = list(table_a.get_model().objects.all())
    assert len(requeried_rows_from_a) == 1
    m2m = getattr(requeried_rows_from_a[0], link_field.db_column)
    assert len(m2m.all()) == 1


@pytest.mark.django_db
@patch("baserow.contrib.database.search.handler.SearchHandler.update_tsvector_columns")
def test_update_tsvector_columns_locked_without_cache_lock(mocked_update, data_fixture):
    table = data_fixture.create_database_table()
    SearchHandler.update_tsvector_columns_locked(
        table, update_tsvectors_for_changed_rows_only=False
    )
    mocked_update.assert_called()


@pytest.mark.django_db
@patch("baserow.contrib.database.search.handler.SearchHandler.update_tsvector_columns")
@patch("baserow.contrib.database.search.handler.cache")
def test_update_tsvector_columns_locked_with_cache_lock_changed_rows_only_false(
    mocked_cache, mocked_update, data_fixture
):
    table = data_fixture.create_database_table()

    # If `update_tsvectors_for_changed_rows_only` is False, we don't expect anything
    # to be locked.
    SearchHandler.update_tsvector_columns_locked(
        table, update_tsvectors_for_changed_rows_only=False
    )
    mocked_cache.lock.assert_not_called()
    mocked_update.assert_called()


@pytest.mark.django_db
@patch("baserow.contrib.database.search.handler.SearchHandler.update_tsvector_columns")
@patch("baserow.contrib.database.search.handler.cache")
def test_update_tsvector_columns_locked_with_cache_lock_changed_rows_only_true_locked(
    mocked_cache, mocked_update, data_fixture
):
    table = data_fixture.create_database_table()

    # If `update_tsvectors_for_changed_rows_only` is False, we expect it to be locked.
    mocked_cache.lock.return_value.locked.return_value = True
    SearchHandler.update_tsvector_columns_locked(
        table, update_tsvectors_for_changed_rows_only=True
    )
    mocked_cache.lock.assert_called_with(
        f"_update_tsvector_columns_update_tsvectors_for_changed_rows_only_{table.id}"
        f"_lock",
        timeout=60 * 60,
    )
    mocked_update.assert_not_called()
    mocked_cache.lock.return_value.release.assert_not_called()


@pytest.mark.django_db
@patch("baserow.contrib.database.search.handler.SearchHandler.update_tsvector_columns")
@patch("baserow.contrib.database.search.handler.cache")
def test_update_tsvector_columns_locked_with_cache_lock_changed_rows_only_true(
    mocked_cache, mocked_update, data_fixture
):
    table = data_fixture.create_database_table()

    # If `update_tsvectors_for_changed_rows_only` is False, we expect it to be locked.
    mocked_cache.lock.return_value.locked.return_value = False
    SearchHandler.update_tsvector_columns_locked(
        table, update_tsvectors_for_changed_rows_only=True
    )
    mocked_cache.lock.assert_called_with(
        f"_update_tsvector_columns_update_tsvectors_for_changed_rows_only_{table.id}"
        f"_lock",
        timeout=60 * 60,
    )
    mocked_update.assert_called()
    mocked_cache.lock.return_value.release.assert_called()


@pytest.mark.django_db
@patch("baserow.contrib.database.search.handler.SearchHandler.update_tsvector_columns")
@patch("baserow.contrib.database.search.handler.cache")
def test_update_tsvector_columns_locked_with_cache_lock_changed_rows_only_true_on_exception(
    mocked_cache, mocked_update, data_fixture
):
    table = data_fixture.create_database_table()

    # If `update_tsvectors_for_changed_rows_only` is False, we expect it to be locked.
    mocked_cache.lock.return_value.locked.return_value = False
    mocked_update.side_effect = Exception()

    with pytest.raises(Exception):
        SearchHandler.update_tsvector_columns_locked(
            table, update_tsvectors_for_changed_rows_only=True
        )
    mocked_cache.lock.assert_called_with(
        f"_update_tsvector_columns_update_tsvectors_for_changed_rows_only_{table.id}"
        f"_lock",
        timeout=60 * 60,
    )
    mocked_cache.lock.return_value.release.assert_called()


@override_settings(TSV_UPDATE_CHUNK_SIZE=2)
@pytest.mark.django_db
def test_split_update_into_chunks_by_ranges(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table, primary=True)

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Test 1"})
    model.objects.create(**{f"field_{field.id}": "Test 2"})
    model.objects.create(**{f"field_{field.id}": "Test 3"})
    model.objects.create(**{f"field_{field.id}": "Test 4"})

    SearchHandler().update_tsvector_columns(table, False)

    rows = model.objects.all()
    assert getattr(rows[0], field.tsv_db_column) == "'1':2 'test':1"
    assert rows[0].needs_background_update is False
    assert getattr(rows[1], field.tsv_db_column) == "'2':2 'test':1"
    assert rows[1].needs_background_update is False
    assert getattr(rows[2], field.tsv_db_column) == "'3':2 'test':1"
    assert rows[2].needs_background_update is False
    assert getattr(rows[3], field.tsv_db_column) == "'4':2 'test':1"
    assert rows[3].needs_background_update is False


@override_settings(TSV_UPDATE_CHUNK_SIZE=2)
@pytest.mark.django_db
def test_split_update_into_chunks_until_all_background_done(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table, primary=True)

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Test 1"})
    model.objects.create(**{f"field_{field.id}": "Test 2"})
    model.objects.create(**{f"field_{field.id}": "Test 3"})
    model.objects.create(**{f"field_{field.id}": "Test 4"})

    SearchHandler().update_tsvector_columns(table, True)

    rows = model.objects.all()
    assert getattr(rows[0], field.tsv_db_column) == "'1':2 'test':1"
    assert rows[0].needs_background_update is False
    assert getattr(rows[1], field.tsv_db_column) == "'2':2 'test':1"
    assert rows[1].needs_background_update is False
    assert getattr(rows[2], field.tsv_db_column) == "'3':2 'test':1"
    assert rows[2].needs_background_update is False
    assert getattr(rows[3], field.tsv_db_column) == "'4':2 'test':1"
    assert rows[3].needs_background_update is False
