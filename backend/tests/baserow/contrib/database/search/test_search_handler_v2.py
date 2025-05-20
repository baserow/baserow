from django.db.models.aggregates import Max

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import ALL_FIELDS, SearchHandler
from baserow.contrib.database.search.types import SearchTableState
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.test_utils.helpers import setup_interesting_test_table
from src.baserow.contrib.database.search.handler import SearchBuilder


@pytest.mark.django_db
def test_create_tsvector_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.DONE},
    )

    model = table.get_model()

    assert len(model.objects.all()) == 2

    SearchHandler.migrate_table_tsvectors(table)
    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    assert len(search_table.objects.all()) == 0
    SearchHandler.update_search_data_for_table(table)
    fields = model.get_field_objects()
    rows = model.objects.all()
    assert search_table
    assert search_table._meta.db_table
    assert len(fields) * len(rows) > 0
    # each field in each row should have an entry
    assert len(search_table.objects.all()) <= len(fields) * len(rows)

    sbuilder = SearchBuilder(table, model)

    sbuilder.add_term("example.com", ALL_FIELDS)

    q = sbuilder.get_queryset()

    assert len(q) == 1


@pytest.mark.django_db
def test_update_tsvector_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.DONE},
    )

    model: GeneratedTableModel = table.get_model()

    assert len(model.objects.all()) == 2

    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)
    SearchHandler.sync_tsvector_columns(table)

    assert len(search_table.objects.all()) == 0
    SearchHandler.update_search_data_for_table(table)
    fields = model.get_field_objects()
    rows = model.objects.all()
    assert search_table
    assert search_table._meta.db_table
    assert len(fields) * len(rows) > 0
    # only fields with search values are counted
    search_items_count = len(search_table.objects.all())
    assert search_items_count <= len(fields) * len(rows)
    max_id = search_table.objects.aggregate(max_id=Max("id")).get("max_id")
    assert max_id is not None and max_id > 0
    # do a full table recalculation
    SearchHandler.update_search_data_for_table(table)

    # +1 row
    new_max_id = search_table.objects.aggregate(max_id=Max("id")).get("max_id")
    assert new_max_id is not None and new_max_id > max_id
    assert new_max_id - max_id <= len(fields) * len(rows)

    # ensure update is queryable
    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("example.com", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 1

    long_text_field = model.get_field_object_by_user_field_name("long_text")
    assert long_text_field
    RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=inserted_row.id,
        values={long_text_field["field"].id: "foobar"},
    )

    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("foobar", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 0

    # do updated row update only
    SearchHandler.update_search_data_for_table(table)

    post_update = len(search_table.objects.all())
    # cleanup
    SearchHandler.cleanup_old_vectors(table)
    post_cleanup = len(search_table.objects.all())

    assert (search_items_count < post_update) and (post_update > post_cleanup)

    # new row values
    assert len(search_table.objects.all()) == post_cleanup

    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("foobar", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 1


@pytest.mark.django_db
def test_update_and_cleanup_tsvector_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, inserted_row, blank_row, context = setup_interesting_test_table(
        data_fixture,
        user,
        database,
        table_kwargs={"search_data_state": SearchTableState.DONE},
    )
    model: GeneratedTableModel = table.get_model()

    assert len(model.objects.all()) == 2

    SearchHandler.sync_tsvector_columns(table)
    search_table = SearchHandler.get_search_table_model(table.database.workspace_id)

    assert len(search_table.objects.all()) == 0
    SearchHandler.update_search_data_for_table(table)
    fields = model.get_field_objects()
    rows = model.objects.all()
    assert search_table
    assert search_table._meta.db_table
    assert len(fields) * len(rows) > 0
    # each field in each row should have an entry
    first_seach_items_count = search_items_count = len(search_table.objects.all())
    assert search_items_count <= len(fields) * len(rows)
    max_id = search_table.objects.aggregate(max_id=Max("id")).get("max_id")
    assert max_id is not None and max_id > 0

    long_text_field = model.get_field_object_by_user_field_name("long_text")
    assert long_text_field
    RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=inserted_row.id,
        values={long_text_field["field"].id: "foobar"},
    )

    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("foobar", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 0

    # do updated row update only
    SearchHandler.update_search_data_for_table(table)

    # new row values included
    search_items_count = len(search_table.objects.all())
    assert search_items_count <= len(fields) * (len(rows) + 1)
    assert search_items_count > first_seach_items_count
    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("foobar", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 1

    SearchHandler.cleanup_old_vectors(table)
    # old row values removed
    search_items_count = len(search_table.objects.all())
    assert search_items_count == first_seach_items_count

    sbuilder = SearchBuilder(table, model)
    sbuilder.add_term("foobar", ALL_FIELDS)
    q = sbuilder.get_queryset()
    assert len(q) == 1
