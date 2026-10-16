from typing import Any, Dict, List, Set, Tuple
from unittest.mock import patch

from django.db import connection
from django.db.models import Case, Value, When
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.contrib.database.fields.dependencies.update_collector import (
    BeforeRowsSnapshot,
    DependantRowsUpdate,
    FieldUpdateCollector,
    PathBasedUpdateStatementCollector,
    merge_dependant_rows_updates,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler
from baserow.test_utils.fixtures import Fixtures


@pytest.mark.django_db
def test_can_add_fields_with_update_statements_in_same_starting_table(
    api_client, data_fixture, django_assert_num_queries
):
    field = data_fixture.create_text_field(name="field")
    model = field.table.get_model(attribute_names=True)
    row = model.objects.create(field="starting value")

    update_collector = FieldUpdateCollector(field.table)
    field_cache = FieldCache()
    update_collector.add_field_with_pending_update_statement(field, Value("other"))
    updated_fields = update_collector.apply_updates_and_get_updated_fields(field_cache)

    assert updated_fields == [field]
    row.refresh_from_db()
    assert row.field == "other"


@pytest.mark.django_db
def test_updates_schedule_search_updates(
    api_client, data_fixture, django_assert_num_queries
):
    # TODO: Fix
    field = data_fixture.create_text_field(name="field")
    model = field.table.get_model(attribute_names=True)
    row = model.objects.create(field="starting value")

    update_collector = FieldUpdateCollector(field.table, starting_row_ids=[row.id])
    field_cache = FieldCache()
    update_collector.add_field_with_pending_update_statement(field, Value("other"))
    updated_fields = update_collector.apply_updates_and_get_updated_fields(field_cache)

    assert updated_fields == [field]
    row.refresh_from_db()


@pytest.mark.django_db
def test_updates_set_them_to_not_need_background_update_when_not_edditing_rows(
    api_client, data_fixture, django_assert_num_queries
):
    # TODO: Fix
    field = data_fixture.create_text_field(name="field")
    model = field.table.get_model(attribute_names=True)
    row = model.objects.create(field="starting value")

    update_collector = FieldUpdateCollector(field.table)
    field_cache = FieldCache()
    update_collector.add_field_with_pending_update_statement(field, Value("other"))
    updated_fields = update_collector.apply_updates_and_get_updated_fields(field_cache)

    assert updated_fields == [field]


@pytest.mark.django_db
def test_can_add_fields_in_same_starting_table_with_row_filter(
    api_client, data_fixture, django_assert_num_queries
):
    field = data_fixture.create_text_field(name="field")
    model = field.table.get_model(attribute_names=True)
    row_a = model.objects.create(field="a")
    row_b = model.objects.create(field="b")

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(field.table, starting_row_ids=[row_a.id])
    update_collector.add_field_with_pending_update_statement(field, Value("other"))
    updated_fields = update_collector.apply_updates_and_get_updated_fields(field_cache)

    assert updated_fields == [field]
    row_a.refresh_from_db()
    row_b.refresh_from_db()
    assert row_a.field == "other"
    assert row_b.field == "b"


@pytest.mark.django_db
def test_can_only_trigger_update_for_rows_joined_to_a_starting_row_across_a_m2m(
    api_client, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    first_table = data_fixture.create_database_table(database=database)
    second_table = data_fixture.create_database_table(database=database)
    first_table_primary_field = data_fixture.create_text_field(
        name="primary", primary=True, table=first_table
    )
    data_fixture.create_text_field(name="primary", primary=True, table=second_table)
    # noinspection PyTypeChecker
    link_row_field: LinkRowField = FieldHandler().create_field(
        user=user,
        table=first_table,
        type_name="link_row",
        link_row_table=second_table,
        name="link",
    )
    first_table_model = first_table.get_model(attribute_names=True)
    second_table_model = second_table.get_model(attribute_names=True)

    second_table_a_row = second_table_model.objects.create(primary="a")
    second_table_b_row = second_table_model.objects.create(primary="b")

    first_table_1_row = first_table_model.objects.create(primary="1")
    first_table_2_row = first_table_model.objects.create(primary="2")

    first_table_1_row.link.add(second_table_a_row.id)
    first_table_1_row.link.add(second_table_b_row.id)
    first_table_1_row.save()

    first_table_2_row.link.add(second_table_b_row.id)
    first_table_2_row.save()

    field_cache = FieldCache()
    with patch(
        "baserow.contrib.database.fields.signals.field_updated.send"
    ) as send_mock:
        update_collector = FieldUpdateCollector(
            second_table,
            starting_row_ids=[second_table_a_row.id],
            # Isolate update-statement queries from the before row snapshot.
            collect_dependant_rows=False,
        )
        update_collector.add_field_with_pending_update_statement(
            first_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[link_row_field],
        )
        # Cache the models so we are only asserting about the update queries
        field_cache.cache_model(first_table.get_model())
        field_cache.cache_model(second_table.get_model())
        # Only one field was updated so only one update statement is expected, plus
        # the query that turns JIT off for it.
        with django_assert_num_queries(2):
            updated_fields = update_collector.apply_updates_and_get_updated_fields(
                field_cache
            )

        # No field in the starting table (second_table) was updated
        assert updated_fields == []
        first_table_1_row.refresh_from_db()
        first_table_2_row.refresh_from_db()
        assert first_table_1_row.primary == "other"
        assert first_table_2_row.primary == "2"

        send_mock.assert_not_called()
        update_collector.send_additional_field_updated_signals()
        send_mock.assert_called_once()
        assert send_mock.call_args[1]["field"].id == first_table_primary_field.id
        assert send_mock.call_args[1]["user"] is None
        assert send_mock.call_args[1]["related_fields"] == []


@pytest.mark.django_db
def test_can_trigger_update_for_rows_joined_to_a_starting_row_across_a_m2m_and_back(
    api_client, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    first_table = data_fixture.create_database_table(database=database)
    second_table = data_fixture.create_database_table(database=database)
    first_table_primary_field = data_fixture.create_text_field(
        name="primary", primary=True, table=first_table
    )
    second_table_primary_field = data_fixture.create_text_field(
        name="primary", primary=True, table=second_table
    )
    # noinspection PyTypeChecker
    link_row_field: LinkRowField = FieldHandler().create_field(
        user=user,
        table=first_table,
        type_name="link_row",
        link_row_table=second_table,
        name="link",
    )
    first_table_model = first_table.get_model(attribute_names=True)
    second_table_model = second_table.get_model(attribute_names=True)

    second_table_a_row = second_table_model.objects.create(primary="a")
    second_table_b_row = second_table_model.objects.create(primary="b")
    second_table_unlinked_row = second_table_model.objects.create(primary="unlinked")

    first_table_1_row = first_table_model.objects.create(primary="1")
    first_table_2_row = first_table_model.objects.create(primary="2")

    first_table_1_row.link.add(second_table_a_row.id)
    first_table_1_row.link.add(second_table_b_row.id)
    first_table_1_row.save()

    first_table_2_row.link.add(second_table_b_row.id)
    first_table_2_row.save()

    with patch(
        "baserow.contrib.database.fields.signals.field_updated.send"
    ) as send_mock:
        field_cache = FieldCache()
        update_collector = FieldUpdateCollector(
            second_table,
            starting_row_ids=[second_table_a_row.id],
            # Isolate update-statement queries from the before row snapshot.
            collect_dependant_rows=False,
        )
        update_collector.add_field_with_pending_update_statement(
            first_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[link_row_field],
        )
        update_collector.add_field_with_pending_update_statement(
            second_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[
                link_row_field,
                link_row_field.link_row_related_field,
            ],
        )
        # Cache the models so we are only asserting about the update queries
        field_cache.cache_model(first_table.get_model())
        field_cache.cache_model(second_table.get_model())
        # Two fields were updated with an update statement for each table
        # Two update statements and one query that turns JIT off for both.
        with django_assert_num_queries(3):
            updated_fields = update_collector.apply_updates_and_get_updated_fields(
                field_cache
            )

        assert updated_fields == [second_table_primary_field]
        first_table_1_row.refresh_from_db()
        first_table_2_row.refresh_from_db()
        second_table_a_row.refresh_from_db()
        second_table_b_row.refresh_from_db()
        second_table_unlinked_row.refresh_from_db()
        assert first_table_1_row.primary == "other"
        assert first_table_2_row.primary == "2"
        assert second_table_a_row.primary == "other"
        assert second_table_b_row.primary == "other"
        assert second_table_unlinked_row.primary == "unlinked"

        send_mock.assert_not_called()
        update_collector.send_additional_field_updated_signals()
        send_mock.assert_called_once()
        assert send_mock.call_args[1]["field"].id == first_table_primary_field.id
        assert send_mock.call_args[1]["user"] is None
        assert send_mock.call_args[1]["related_fields"] == []


@pytest.mark.django_db
def test_update_statements_at_the_same_path_node_are_grouped_into_one(
    api_client, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    first_table = data_fixture.create_database_table(database=database)
    second_table = data_fixture.create_database_table(database=database)
    first_table_primary_field = data_fixture.create_text_field(
        name="primary", primary=True, table=first_table
    )
    first_table_other_field = data_fixture.create_text_field(
        name="other", table=first_table
    )
    second_table_primary_field = data_fixture.create_text_field(
        name="primary", primary=True, table=second_table
    )
    # noinspection PyTypeChecker
    link_row_field: LinkRowField = FieldHandler().create_field(
        user=user,
        table=first_table,
        type_name="link_row",
        link_row_table=second_table,
        name="link",
    )
    first_table_model = first_table.get_model(attribute_names=True)
    second_table_model = second_table.get_model(attribute_names=True)

    second_table_a_row = second_table_model.objects.create(primary="a")
    second_table_b_row = second_table_model.objects.create(primary="b")
    second_table_unlinked_row = second_table_model.objects.create(primary="unlinked")

    first_table_1_row = first_table_model.objects.create(primary="1", other="x")
    first_table_2_row = first_table_model.objects.create(primary="2", other="y")

    first_table_1_row.link.add(second_table_a_row.id)
    first_table_1_row.link.add(second_table_b_row.id)
    first_table_1_row.save()

    first_table_2_row.link.add(second_table_b_row.id)
    first_table_2_row.save()

    with patch(
        "baserow.contrib.database.fields.signals.field_updated.send"
    ) as send_mock:
        field_cache = FieldCache()
        update_collector = FieldUpdateCollector(
            second_table,
            starting_row_ids=[second_table_a_row.id],
            # Isolate update-statement queries from the before row snapshot.
            collect_dependant_rows=False,
        )
        update_collector.add_field_with_pending_update_statement(
            first_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[link_row_field],
        )
        update_collector.add_field_with_pending_update_statement(
            first_table_other_field,
            Value("updated"),
            via_path_to_starting_table=[link_row_field],
        )
        update_collector.add_field_with_pending_update_statement(
            second_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[
                link_row_field,
                link_row_field.link_row_related_field,
            ],
        )
        # Cache the models so we are only asserting about the update queries
        field_cache.cache_model(first_table.get_model())
        field_cache.cache_model(second_table.get_model())
        # Three fields were updated but two are in the same path node (same table) and
        # so only one update per table expected
        # Two update statements and one query that turns JIT off for both.
        with django_assert_num_queries(3):
            updated_fields = update_collector.apply_updates_and_get_updated_fields(
                field_cache
            )

        assert updated_fields == [second_table_primary_field]
        first_table_1_row.refresh_from_db()
        first_table_2_row.refresh_from_db()
        second_table_a_row.refresh_from_db()
        second_table_b_row.refresh_from_db()
        second_table_unlinked_row.refresh_from_db()
        assert first_table_1_row.primary == "other"
        assert first_table_1_row.other == "updated"
        assert first_table_2_row.primary == "2"
        assert first_table_2_row.other == "y"
        assert second_table_a_row.primary == "other"
        assert second_table_b_row.primary == "other"
        assert second_table_unlinked_row.primary == "unlinked"

        send_mock.assert_not_called()
        update_collector.send_additional_field_updated_signals()
        send_mock.assert_called_once()
        assert send_mock.call_args[1]["field"].id == first_table_primary_field.id
        assert send_mock.call_args[1]["user"] is None
        assert send_mock.call_args[1]["related_fields"] == [first_table_other_field]


@pytest.mark.django_db
def test_update_statements_only_update_rows_where_values_change(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    text_field = data_fixture.create_text_field(name="text", table=table)
    table_model = table.get_model()

    row_1 = table_model.objects.create(**{f"field_{text_field.id}": "a"})
    row_2 = table_model.objects.create(**{f"field_{text_field.id}": "a"})
    row_3 = table_model.objects.create(**{f"field_{text_field.id}": "b"})

    def execute_update_statement(update_statement):
        update_collector = FieldUpdateCollector(table, update_changes_only=True)
        field_cache = FieldCache()
        via_path_to_starting_table = []

        update_collector.add_field_with_pending_update_statement(
            text_field,
            update_statement,
            via_path_to_starting_table,
        )
        field_cache.cache_model(table_model)
        updated_rows = update_collector.apply_updates(field_cache)
        return updated_rows

    def assert_all_rows_have_value(value):
        for row in table_model.objects.all():
            assert getattr(row, f"field_{text_field.id}") == value

    # only the row with value "b" should be updated
    result = execute_update_statement(Value("a"))
    assert result[table.id] == {row_3.id}
    assert_all_rows_have_value("a")

    row_4 = table_model.objects.create(**{f"field_{text_field.id}": "b"})
    row_5 = table_model.objects.create(**{f"field_{text_field.id}": "b"})

    func_update_statement = Case(
        When(
            **{"id__in": [row_1.id, row_2.id, row_3.id, row_4.id, row_5.id]},
            then=Value("a"),
        ),
        default=Value("b"),
    )

    # Only row_4 and row_5 should be updated, the others already have the value "a"
    result = execute_update_statement(func_update_statement)
    assert result[table.id] == {row_4.id, row_5.id}
    assert_all_rows_have_value("a")


@pytest.mark.django_db
def test_apply_updates_returns_only_last_updated_fields_but_update_collector_track_all_changes(
    api_client, data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_1 = data_fixture.create_database_table(database=database)
    t1_field1 = data_fixture.create_text_field(name="f1", table=table_1)
    t1_field2 = data_fixture.create_text_field(name="f2", table=table_1)
    t1_model = table_1.get_model(attribute_names=True)
    t1_row = t1_model.objects.create(f1="starting value 1", f2="starting value 2")

    # Setup another table with a field referencing field_1
    table_2 = data_fixture.create_database_table(database=database)
    t2_link_t1 = data_fixture.create_link_row_field(
        table=table_2, link_row_table=table_1, name="link_t2"
    )
    t2_field1 = data_fixture.create_text_field(name="f1", table=table_2)
    t2_model = table_2.get_model(attribute_names=True)
    t2_row = t2_model.objects.create(f1="starting value t2")

    # Setup another table with a field referencing field_2
    table_3 = data_fixture.create_database_table(database=database)
    t3_link_t1 = data_fixture.create_link_row_field(
        table=table_3, link_row_table=table_1, name="link_t3"
    )
    t3_field1 = data_fixture.create_text_field(name="f1", table=table_3)
    t3_model = table_3.get_model(attribute_names=True)
    t3_row = t3_model.objects.create(f1="starting value t3")

    # First call to apply_updates_and_get_updated_fields to update table_1 and table_2
    update_collector = FieldUpdateCollector(table_1)
    field_cache = FieldCache()
    update_collector.add_field_with_pending_update_statement(
        t1_field1, Value("other 1")
    )
    update_collector.add_field_with_pending_update_statement(
        t2_field1, Value("other 1"), via_path_to_starting_table=[t2_link_t1]
    )
    updated_fields_in_table = update_collector.apply_updates_and_get_updated_fields(
        field_cache
    )

    assert updated_fields_in_table == [t1_field1]
    t1_row.refresh_from_db()
    assert t1_row.f1 == "other 1"
    assert t1_row.f2 == "starting value 2"
    t2_row.refresh_from_db()
    assert t2_row.f1 == "other 1"
    t3_row.refresh_from_db()
    assert t3_row.f1 == "starting value t3"

    # Second call to apply_updates_and_get_updated_fields to update table_1 and table_3
    update_collector.add_field_with_pending_update_statement(
        t1_field2, Value("other 2")
    )
    update_collector.add_field_with_pending_update_statement(
        t3_field1, Value("other 2"), via_path_to_starting_table=[t3_link_t1]
    )
    updated_fields_in_table = update_collector.apply_updates_and_get_updated_fields(
        field_cache
    )

    assert updated_fields_in_table == [t1_field2]
    t1_row.refresh_from_db()
    assert t1_row.f1 == "other 1"
    assert t1_row.f2 == "other 2"
    t2_row.refresh_from_db()
    assert t2_row.f1 == "other 1"
    t3_row.refresh_from_db()
    assert t3_row.f1 == "other 2"

    # Despite the multiple calls to apply_updates_and_get_updated_fields, the update
    # collector should have tracked all changes and can send the signals for all of them
    with patch("baserow.contrib.database.table.signals.table_updated.send") as mock:
        update_collector.send_force_refresh_signals_for_all_updated_tables()

        assert mock.call_count == 3
        assert mock.call_args_list[0][1]["table"].id == table_1.id
        assert mock.call_args_list[1][1]["table"].id == table_2.id
        assert mock.call_args_list[2][1]["table"].id == table_3.id


@pytest.mark.django_db
def test_get_dependant_rows_updates_finds_rows_of_marked_only_link_fields(
    data_fixture,
):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    row_b1 = table_b_model.objects.create(primary="b1")
    row_b2 = table_b_model.objects.create(primary="b2")
    a_linked_to_b1 = table_a_model.objects.create(primary="1")
    a_also_linked_to_b1 = table_a_model.objects.create(primary="2")
    a_linked_to_b2 = table_a_model.objects.create(primary="3")
    a_linked_to_b1.link.add(row_b1.id)
    a_also_linked_to_b1.link.add(row_b1.id)
    a_linked_to_b2.link.add(row_b2.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table_b, starting_row_ids=[row_b1.id])
    update_collector.add_field_which_has_changed(
        link_field, via_path_to_starting_table=[link_field]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    updates = update_collector.get_dependant_rows_updates()
    assert len(updates) == 1
    assert updates[0].table.id == table_a.id
    assert updates[0].row_ids == sorted([a_linked_to_b1.id, a_also_linked_to_b1.id])
    assert updates[0].field_ids == [link_field.id]
    assert updates[0].requires_refresh is False


@pytest.mark.django_db
def test_get_dependant_rows_updates_deduplicates_relations_before_the_limit(
    data_fixture,
):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    starting_rows = [table_b_model.objects.create(primary=str(i)) for i in range(5)]
    row_a1 = table_a_model.objects.create(primary="1")
    row_a2 = table_a_model.objects.create(primary="2")
    for starting_row in starting_rows:
        row_a1.link.add(starting_row.id)
        row_a2.link.add(starting_row.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(
        table_b, starting_row_ids=[row.id for row in starting_rows]
    )
    update_collector.add_field_which_has_changed(
        link_field, via_path_to_starting_table=[link_field]
    )
    # 10 m2m relations point back to the starting rows but only 2 distinct rows
    # exist, which is within the limit of 3.
    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=3):
        update_collector.apply_updates_and_get_updated_fields(field_cache)
        updates = update_collector.get_dependant_rows_updates()

    assert len(updates) == 1
    assert updates[0].row_ids == sorted([row_a1.id, row_a2.id])
    assert updates[0].requires_refresh is False


@pytest.mark.django_db
def test_get_dependant_rows_updates_requires_refresh_over_the_limit(data_fixture):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    row_b = table_b_model.objects.create(primary="b")
    for i in range(3):
        row_a = table_a_model.objects.create(primary=str(i))
        row_a.link.add(row_b.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table_b, starting_row_ids=[row_b.id])
    update_collector.add_field_which_has_changed(
        link_field, via_path_to_starting_table=[link_field]
    )
    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=2):
        update_collector.apply_updates_and_get_updated_fields(field_cache)
        updates = update_collector.get_dependant_rows_updates()

    assert len(updates) == 1
    assert updates[0].table.id == table_a.id
    assert updates[0].row_ids == []
    assert updates[0].requires_refresh is True


@pytest.mark.django_db
def test_get_dependant_rows_updates_returns_nothing_when_disabled(data_fixture):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    row_b = table_b_model.objects.create(primary="b")
    row_a = table_a_model.objects.create(primary="1")
    row_a.link.add(row_b.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table_b, starting_row_ids=[row_b.id])
    update_collector.add_field_which_has_changed(
        link_field, via_path_to_starting_table=[link_field]
    )
    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=0):
        update_collector.apply_updates_and_get_updated_fields(field_cache)
        assert update_collector.get_dependant_rows_updates() == []


@pytest.mark.django_db
def test_get_dependant_rows_updates_excludes_starting_rows_from_update_statements(
    data_fixture,
):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_b_field = data_fixture.create_text_field(name="other", table=table_b)
    table_a_field = data_fixture.create_text_field(name="other", table=table_a)
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    row_b = table_b_model.objects.create(primary="b")
    a_linked = table_a_model.objects.create(primary="1")
    a_unlinked = table_a_model.objects.create(primary="2")
    a_linked.link.add(row_b.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table_b, starting_row_ids=[row_b.id])
    update_collector.add_field_with_pending_update_statement(
        table_b_field, Value("changed")
    )
    update_collector.add_field_with_pending_update_statement(
        table_a_field,
        Value("changed"),
        via_path_to_starting_table=[link_field],
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    updates = update_collector.get_dependant_rows_updates()
    # The starting table entry is dropped: its only updated row is a starting
    # row, already broadcast by the regular row signals.
    assert len(updates) == 1
    assert updates[0].table.id == table_a.id
    assert updates[0].row_ids == [a_linked.id]
    assert updates[0].field_ids == [table_a_field.id]
    assert updates[0].requires_refresh is False
    assert a_unlinked.id not in updates[0].row_ids


@pytest.mark.django_db
def test_get_dependant_rows_updates_accumulates_across_apply_updates_calls(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    table_c = data_fixture.create_database_table(database=table_a.database)
    data_fixture.create_text_field(name="primary", primary=True, table=table_c)
    table_c_link: LinkRowField = FieldHandler().create_field(
        user=user,
        table=table_c,
        type_name="link_row",
        link_row_table=table_b,
        name="link",
    )
    table_a_field = data_fixture.create_text_field(name="other", table=table_a)
    table_c_field = data_fixture.create_text_field(name="other", table=table_c)

    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)
    table_c_model = table_c.get_model(attribute_names=True)
    row_b = table_b_model.objects.create(primary="b")
    row_a = table_a_model.objects.create(primary="1")
    row_c = table_c_model.objects.create(primary="1")
    row_a.link.add(row_b.id)
    row_c.link.add(row_b.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table_b, starting_row_ids=[row_b.id])
    update_collector.add_field_with_pending_update_statement(
        table_a_field, Value("level 0"), via_path_to_starting_table=[link_field]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)
    update_collector.add_field_with_pending_update_statement(
        table_c_field, Value("level 1"), via_path_to_starting_table=[table_c_link]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    updates = {u.table.id: u for u in update_collector.get_dependant_rows_updates()}
    assert set(updates.keys()) == {table_a.id, table_c.id}
    assert updates[table_a.id].row_ids == [row_a.id]
    assert updates[table_c.id].row_ids == [row_c.id]


@pytest.mark.django_db
def test_get_dependant_rows_updates_self_link_finds_rows_linking_to_starting_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="primary", primary=True, table=table)
    self_link: LinkRowField = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=table,
        name="self link",
    )
    model = table.get_model()

    row_a = model.objects.create()
    row_b = model.objects.create()
    row_unrelated = model.objects.create()
    getattr(row_b, self_link.db_column).add(row_a.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table, starting_row_ids=[row_a.id])
    update_collector.add_field_which_has_changed(
        self_link, via_path_to_starting_table=[self_link]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    updates = update_collector.get_dependant_rows_updates()
    # Row b displays row a through the self link, so it needs a realtime
    # update; row a itself is a starting row and row_unrelated links nothing.
    assert len(updates) == 1
    assert updates[0].table.id == table.id
    assert updates[0].row_ids == [row_b.id]
    assert row_unrelated.id not in updates[0].row_ids


@pytest.mark.django_db
def test_get_dependant_rows_updates_includes_rows_with_deleted_m2m_relationships(
    data_fixture,
):
    table_a, table_b, link_field = data_fixture.create_two_linked_tables()
    table_a_model = table_a.get_model(attribute_names=True)
    table_b_model = table_b.get_model(attribute_names=True)

    row_b = table_b_model.objects.create(primary="b")
    # This row just lost its connection to the starting row, so the m2m join
    # can't find it and it must come from the deleted relationships instead.
    a_unlinked_row = table_a_model.objects.create(primary="1")

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(
        table_b,
        starting_row_ids=[row_b.id],
        deleted_m2m_rels_per_link_field={
            link_field.link_row_related_field_id: {a_unlinked_row.id}
        },
    )
    update_collector.add_field_which_has_changed(
        link_field, via_path_to_starting_table=[link_field]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    updates = update_collector.get_dependant_rows_updates()
    assert len(updates) == 1
    assert updates[0].table.id == table_a.id
    assert updates[0].row_ids == [a_unlinked_row.id]


@pytest.mark.django_db
def test_self_link_update_statements_also_update_rows_linking_to_starting_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(name="primary", primary=True, table=table)
    other_field = data_fixture.create_text_field(name="other", table=table)
    self_link: LinkRowField = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        link_row_table=table,
        name="self link",
    )
    model = table.get_model()

    row_a = model.objects.create()
    row_b = model.objects.create()
    getattr(row_b, self_link.db_column).add(row_a.id)

    field_cache = FieldCache()
    update_collector = FieldUpdateCollector(table, starting_row_ids=[row_a.id])
    update_collector.add_field_with_pending_update_statement(
        other_field, Value("changed"), via_path_to_starting_table=[self_link]
    )
    update_collector.add_field_which_has_changed(
        self_link, via_path_to_starting_table=[self_link]
    )
    update_collector.apply_updates_and_get_updated_fields(field_cache)

    # Both the starting row (its own cells read through the link) and the rows
    # linking to it must be recalculated.
    row_a.refresh_from_db()
    row_b.refresh_from_db()
    assert getattr(row_a, other_field.db_column) == "changed"
    assert getattr(row_b, other_field.db_column) == "changed"

    updates = update_collector.get_dependant_rows_updates()
    assert len(updates) == 1
    assert updates[0].row_ids == [row_b.id]


class _CascadeIntoFilteredView:
    """Rows linked to a starting row, in a table whose public view filters them."""

    def __init__(self, data_fixture: Fixtures, filtered_values: List[str]) -> None:
        self.table, starting_table, self.link_field = (
            data_fixture.create_two_linked_tables()
        )
        self.filtered_field = data_fixture.create_text_field(table=self.table)
        self.other_field = data_fixture.create_text_field(table=self.table)
        self.view = data_fixture.create_grid_view(table=self.table, public=True)
        data_fixture.create_view_filter(
            view=self.view, field=self.filtered_field, type="equal", value="match"
        )
        self.starting_row_id = starting_table.get_model().objects.create().id
        self.collector = FieldUpdateCollector(
            starting_table, starting_row_ids=[self.starting_row_id]
        )
        self.model = self.table.get_model()
        self.rows = [self.create_row(value) for value in filtered_values]
        for row in self.rows:
            self.link(row)

    def create_row(self, value: str) -> GeneratedTableModel:
        return self.model.objects.create(**{self.filtered_field.db_column: value})

    def link(self, row: GeneratedTableModel) -> None:
        getattr(row, self.link_field.db_column).add(self.starting_row_id)

    def apply(self, field: Field, value: str) -> List[str]:
        self.collector.add_field_with_pending_update_statement(
            field, Value(value), via_path_to_starting_table=[self.link_field]
        )
        with CaptureQueriesContext(connection) as captured:
            self.collector.apply_updates_and_get_updated_fields(FieldCache())
        return [query["sql"] for query in captured.captured_queries]

    def get_snapshot_reads(self, sqls: List[str]) -> List[str]:
        table_sql = f'FROM "{self.table.get_database_table_name()}" WHERE '
        # The visibility query of the checked views reads the table too.
        return [
            sql
            for sql in sqls
            if sql.startswith("SELECT") and table_sql in sql and "visible_v" not in sql
        ]


@pytest.mark.django_db
@override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=4)
def test_snapshot_never_captures_a_row_twice_nor_after_the_cascade_changed_it(
    data_fixture,
):
    cascade = _CascadeIntoFilteredView(data_fixture, ["nope", "nope"])
    first, second = cascade.rows
    late, later = cascade.create_row("match"), cascade.create_row("match")
    execute_update_statements = (
        PathBasedUpdateStatementCollector._execute_pending_update_statements
    )

    def link_late_row_before_updating(
        collector: PathBasedUpdateStatementCollector, *args: Any, **kwargs: Any
    ) -> List[int]:
        if collector.table.id == cascade.table.id:
            cascade.link(late)
        return execute_update_statements(collector, *args, **kwargs)

    # As if another transaction committed the link between the snapshot and UPDATE.
    with patch.object(
        PathBasedUpdateStatementCollector,
        "_execute_pending_update_statements",
        autospec=True,
        side_effect=link_late_row_before_updating,
    ):
        cascade.apply(cascade.filtered_field, "match")
    cascade.link(later)
    cascade.apply(cascade.other_field, "changed")

    [update] = cascade.collector.get_dependant_rows_updates()
    assert update.row_ids == [first.id, second.id, late.id, later.id]
    # later fits the limit only because the rows not to snapshot are skipped first.
    assert update.before_rows.keys() == {first.id, second.id, later.id}
    assert update.before_rows[first.id][cascade.filtered_field.db_column] == "nope"
    visible = update.before_visible_view_ids
    assert visible == {first.id: set(), second.id: set(), later.id: {cascade.view.id}}
    assert update.before_checked_view_ids == {cascade.view.id}


def _create_rows_linked_through_each_path_shape(
    data_fixture: Fixtures,
) -> Tuple[Dict[str, List[LinkRowField]], Dict[str, GeneratedTableModel]]:
    """Creates named rows linked to a starting table by a self link, one or two hops."""

    user = data_fixture.create_user()
    middle, start, middle_link = data_fixture.create_two_linked_tables(user=user)
    end, _, end_link = data_fixture.create_two_linked_tables(user=user, table_b=middle)
    self_link = data_fixture.create_link_row_field(table=start, link_row_table=start)
    paths = {"self": [self_link], "middle": [middle_link]}
    paths["end"] = [end_link, middle_link]
    paths["middle_and_back"] = [middle_link, middle_link.link_row_related_field]
    models = {table.id: table.get_model() for table in (start, middle, end)}
    rows: Dict[str, GeneratedTableModel] = {}
    for name, path_name, linked_row_names in [
        ("linked_by_start", "self", []),
        ("start", "self", ["linked_by_start"]),
        ("other_start", "self", []),
        ("linking_to_start", "self", ["start"]),
        ("linked", "middle", ["start"]),
        ("linked_to_both", "middle", ["start", "other_start"]),
        ("trashed", "middle", ["start"]),
        ("unlinked", "middle", []),
        ("deleted", "middle", ["other_start"]),
        ("linked_twice", "end", ["linked", "linked_to_both"]),
        ("via_trashed", "end", ["trashed"]),
        ("via_unlinked", "end", ["unlinked"]),
        ("via_deleted", "end", ["deleted"]),
    ]:
        link = paths[path_name][0]
        rows[name] = models[link.table_id].objects.create(trashed=name == "trashed")
        getattr(rows[name], link.db_column).add(*[rows[n].id for n in linked_row_names])
    # Like a batch permanent deletion, which leaves the row's relations behind.
    deleted_rows = models[middle.id].objects.filter(id=rows["deleted"].id)
    deleted_rows._raw_delete(connection.alias)
    return paths, rows


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path_name,starting_row_names,removes_link,expected_row_names",
    [
        ("middle", ["start"], False, ["linked", "linked_to_both"]),
        ("end", ["start"], False, ["linked_twice", "via_trashed"]),
        ("self", ["start"], False, ["linking_to_start"]),
        ("middle", ["start"], True, ["linked", "linked_to_both", "unlinked"]),
        ("end", ["start"], True, ["linked_twice", "via_trashed", "via_unlinked"]),
        ("middle", ["start", "other_start"], False, ["linked", "linked_to_both"]),
        ("end", ["other_start"], False, ["linked_twice"]),
        ("middle_and_back", ["linked"], False, ["linked", "linked_to_both"]),
    ],
    ids=[
        "one_hop",
        "two_hops",
        "self_link",
        "removed_link_on_one_hop",
        "removed_link_on_two_hops",
        "row_linked_to_several_starting_rows",
        "orphaned_relation_of_a_permanently_deleted_middle_row",
        "link_and_back_through_the_lazily_built_reverse_relation",
    ],
)
def test_snapshot_statement_selects_the_cascade_filter_rows(
    data_fixture,
    path_name: str,
    starting_row_names: List[str],
    removes_link: bool,
    expected_row_names: List[str],
):
    paths, rows = _create_rows_linked_through_each_path_shape(data_fixture)
    path = paths[path_name]
    model = path[0].table.get_model()
    starting_row_ids = [rows[name].id for name in starting_row_names]
    removed_link_row_ids = {rows["unlinked"].id} if removes_link else set()
    deleted_rels = {path[-1].link_row_related_field_id: removed_link_row_ids}
    collector = PathBasedUpdateStatementCollector(
        model.baserow_table, connection_here=path[0], connection_is_broken=False
    )
    snapshot = BeforeRowsSnapshot(needs_view_checks=True)

    selected_row_ids = [
        [
            row.id
            for row in collector._read_rows_to_snapshot(
                model, row_filter, set(), 100, snapshot, None
            )
        ]
        for row_filter in collector._filters_for_rows_to_snapshot(
            model, path, starting_row_ids, deleted_rels
        )
    ]
    # Ordered by id and listed once, while the cascade filter's joins repeat rows.
    assert selected_row_ids == [
        sorted(set(model.objects.filter(row_filter).values_list("id", flat=True)))
        for row_filter in collector._filters_for_rows_connected_to_starting_rows(
            path, starting_row_ids, deleted_rels, include_starting_rows=False
        )
    ]
    assert sorted(sum(selected_row_ids, [])) == sorted(
        rows[name].id for name in expected_row_names
    )


@pytest.mark.django_db
@pytest.mark.parametrize("a_view_needs_checks", [True, False])
def test_snapshot_reads_the_link_tables_and_locks_only_when_a_view_needs_checks(
    data_fixture, a_view_needs_checks: bool
):
    cascade = _CascadeIntoFilteredView(data_fixture, ["nope"])
    field = cascade.filtered_field if a_view_needs_checks else cascade.other_field
    cascade.collector.set_dependant_fields([field])
    sqls = cascade.apply(field, "match")

    reads = cascade.get_snapshot_reads(sqls)
    assert all("= ANY(ARRAY(" in sql and "IN (SELECT" not in sql for sql in reads)
    # The first read tells whether a view needs checks, only then rows are locked.
    lock = f'FOR UPDATE OF "{cascade.table.get_database_table_name()}"'
    expected_locks = [False, True] if a_view_needs_checks else [False]
    assert [lock in sql for sql in reads] == expected_locks
    assert sum("FOR UPDATE" in sql for sql in sqls) == expected_locks.count(True)


@pytest.mark.django_db
@override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=2)
def test_snapshot_work_stops_once_the_table_overflows(data_fixture):
    cascade = _CascadeIntoFilteredView(data_fixture, ["nope"] * 3)
    with patch.object(
        ViewRealtimeRowsHandler, "get_checked_views_row_checker"
    ) as get_row_checker:
        sqls = cascade.apply(cascade.filtered_field, "match")
        sqls += cascade.apply(cascade.other_field, "changed")

    [update] = cascade.collector.get_dependant_rows_updates()
    assert update.requires_refresh is True
    assert get_row_checker.call_count == 0
    assert not any("FOR UPDATE" in sql or "visible_v" in sql for sql in sqls)
    # The second depth level skips the snapshot of the overflowed table.
    assert len(cascade.get_snapshot_reads(sqls)) == 1
    snapshot = cascade.collector._before_snapshots_per_table[cascade.table.id]
    assert snapshot.rows == {} and snapshot.row_ids_updated_without_snapshot == set()


@pytest.mark.django_db
def test_snapshot_records_the_fields_with_unknown_before_values_of_each_level(
    data_fixture,
):
    cascade = _CascadeIntoFilteredView(data_fixture, ["nope"])
    path = [cascade.link_field]
    cascade.collector.add_field_which_has_changed(cascade.link_field, path)
    cascade.apply(cascade.filtered_field, "match")
    cascade.collector.add_field_which_has_changed(cascade.other_field, path)
    cascade.collector.apply_updates_and_get_updated_fields(FieldCache())

    [update] = cascade.collector.get_dependant_rows_updates()
    unknown_field_ids = {cascade.link_field.id, cascade.other_field.id}
    assert update.field_ids_with_unknown_before_values == unknown_field_ids


def _dependant_rows_updates(
    field_id: int, row_ids: List[int], visible_view_ids: Dict[int, Set[int]]
) -> List[DependantRowsUpdate]:
    """An update of a field with unknown before values, snapshotting the given rows."""

    return [
        DependantRowsUpdate(
            table=Table(id=1),
            row_ids=row_ids,
            field_ids=[field_id],
            requires_refresh=False,
            field_ids_with_unknown_before_values={field_id},
            before_rows={row_id: {"field_id": field_id} for row_id in visible_view_ids},
            before_visible_view_ids=visible_view_ids,
            before_checked_view_ids={100},
        )
    ]


def test_merge_dependant_rows_updates_keeps_the_earliest_snapshot_until_the_limit():
    [merged] = merge_dependant_rows_updates(
        _dependant_rows_updates(10, [1], {}),
        _dependant_rows_updates(11, [1, 2], {1: {100}, 2: {100}}),
        _dependant_rows_updates(12, [2], {2: set()}),
    )
    assert merged.row_ids == [1, 2]
    # Row 1's later snapshot would show it after the first update changed it.
    assert merged.before_rows == {2: {"field_id": 11}}
    assert merged.before_visible_view_ids == {2: {100}}
    assert merged.field_ids_with_unknown_before_values == {10, 11, 12}

    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=1):
        [overflowed] = merge_dependant_rows_updates(
            _dependant_rows_updates(10, [1], {1: {100}}),
            _dependant_rows_updates(11, [2], {2: {100}}),
        )
    assert overflowed.requires_refresh is True
    assert overflowed.before_rows == {} and overflowed.before_visible_view_ids == {}
    assert overflowed.before_checked_view_ids == set()
    assert overflowed.field_ids_with_unknown_before_values == {10, 11}
