from unittest.mock import patch

from django.db.models import Case, Value, When
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.dependencies.update_collector import (
    FieldUpdateCollector,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import LinkRowField


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
            second_table, starting_row_ids=[second_table_a_row.id]
        )
        update_collector.add_field_with_pending_update_statement(
            first_table_primary_field,
            Value("other"),
            via_path_to_starting_table=[link_row_field],
        )
        # Cache the models so we are only asserting about the update queries
        field_cache.cache_model(first_table.get_model())
        field_cache.cache_model(second_table.get_model())
        # Only one field was updated so only one update statement is expected
        with django_assert_num_queries(1):
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
            second_table, starting_row_ids=[second_table_a_row.id]
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
        with django_assert_num_queries(2):
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
            second_table, starting_row_ids=[second_table_a_row.id]
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
        with django_assert_num_queries(2):
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
