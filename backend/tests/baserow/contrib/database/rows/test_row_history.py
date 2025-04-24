from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.history import RowHistoryHandler
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.registries import (
    ChangeRowHistoryType,
    change_row_history_registry,
)
from baserow.core.action.registries import action_type_registry


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_insert_multiple_entries_in_row_history(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    row_handler = RowHandler()

    row_one = row_handler.force_create_row(user, table, {name_field.id: "Original 1"})
    row_two = row_handler.force_create_row(user, table, {name_field.id: "Original 2"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row_one.id, f"field_{name_field.id}": "New 1"},
                {"id": row_two.id, f"field_{name_field.id}": "New 2"},
            ],
        )
    assert RowHistory.objects.count() == 2

    history_entries = RowHistory.objects.order_by("row_id").values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    assert list(history_entries) == [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table.id,
            "row_id": row_one.id,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {f"field_{name_field.id}": "Original 1"},
            "after_values": {f"field_{name_field.id}": "New 1"},
            "fields_metadata": {
                f"field_{name_field.id}": {
                    "type": "text",
                    "id": name_field.id,
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table.id,
            "row_id": row_two.id,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {f"field_{name_field.id}": "Original 2"},
            "after_values": {f"field_{name_field.id}": "New 2"},
            "fields_metadata": {
                f"field_{name_field.id}": {
                    "type": "text",
                    "id": name_field.id,
                }
            },
        },
    ]


@pytest.mark.django_db
@pytest.mark.row_history
def test_history_handler_only_save_changed_fields(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )

    row_handler = RowHandler()

    row = row_handler.force_create_row(user, table, {name_field.id: "Original 1"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {
                    "id": row.id,
                    f"field_{name_field.id}": "New 1",
                    f"field_{number_field.id}": None,
                }
            ],
        )

    assert RowHistory.objects.count() == 1

    history_entries = RowHistory.objects.values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    assert list(history_entries) == [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table.id,
            "row_id": row.id,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {
                f"field_{name_field.id}": "Original 1",
            },
            "after_values": {f"field_{name_field.id}": "New 1"},
            "fields_metadata": {
                f"field_{name_field.id}": {
                    "type": "text",
                    "id": name_field.id,
                }
            },
        },
    ]


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_action_doesnt_insert_entries_if_row_doesnt_change(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )

    row_handler = RowHandler()

    row_one = row_handler.force_create_row(user, table, {name_field.id: "Original 1"})
    row_two = row_handler.force_create_row(user, table, {name_field.id: "Original 2"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row_one.id, f"field_{name_field.id}": "New 1"},
                {"id": row_two.id, f"field_{name_field.id}": "Original 2"},
            ],
        )

    # This does not insert any entries in the row history table because no values
    # have changed.
    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [{"id": row_one.id, f"field_{name_field.id}": "New 1"}],
        )

    assert RowHistory.objects.count() == 1
    history_entries = RowHistory.objects.order_by("row_id").values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )
    assert list(history_entries) == [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table.id,
            "row_id": row_one.id,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {f"field_{name_field.id}": "Original 1"},
            "after_values": {f"field_{name_field.id}": "New 1"},
            "fields_metadata": {
                f"field_{name_field.id}": {
                    "type": "text",
                    "id": name_field.id,
                }
            },
        }
    ]


@pytest.mark.django_db
@pytest.mark.row_history
def test_row_history_handler_list_history_filters_with_registry(data_fixture):
    """
    Test that queryset filtering is sourced from RowHistoryOperationsRegistry.
    """

    class FilterRowHistoryStub(ChangeRowHistoryType):
        type = "row_history_op_stub"

        def apply_to_list_queryset(self, queryset, workspace, table_id, row_id):
            return queryset.filter(user_id__lt=2)

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    common_params = {
        "table": table,
        "row_id": 999,
        "action_uuid": "uuid",
        "action_command_type": "cmd",
        "action_type": "type",
        "field_names": [],
        "fields_metadata": {},
        "before_values": {},
        "after_values": {},
        "action_timestamp": datetime(2021, 1, 3, 23, 59, tzinfo=timezone.utc),
    }
    entries = [RowHistory(**common_params, user_id=i) for i in range(0, 10)]
    RowHistory.objects.bulk_create(entries)
    assert (
        len(
            RowHistoryHandler().list_row_history(
                database.workspace, table.id, row_id=999
            )
        )
        == 10
    )

    change_row_history_registry.register(FilterRowHistoryStub())
    assert (
        len(
            RowHistoryHandler().list_row_history(
                database.workspace, table.id, row_id=999
            )
        )
        == 2
    )

    change_row_history_registry.unregister("row_history_op_stub")


@pytest.mark.django_db
@pytest.mark.row_history
def test_row_history_handler_delete_entries_older_than(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    before_retention_period = datetime(2021, 1, 3, 23, 59, tzinfo=timezone.utc)
    after_retention_period = datetime(2021, 1, 4, 0, 1, tzinfo=timezone.utc)
    cutoff = datetime(2021, 1, 4, 0, 0, tzinfo=timezone.utc)
    common_params = {
        "table": table,
        "row_id": 999,
        "action_uuid": "uuid",
        "action_command_type": "cmd",
        "action_type": "type",
        "field_names": [],
        "fields_metadata": {},
        "before_values": {},
        "after_values": {},
    }
    entries = [
        RowHistory(**common_params, action_timestamp=before_retention_period),
        RowHistory(**common_params, action_timestamp=before_retention_period),
        RowHistory(**common_params, action_timestamp=before_retention_period),
        RowHistory(**common_params, action_timestamp=after_retention_period),
        RowHistory(**common_params, action_timestamp=after_retention_period),
    ]
    RowHistory.objects.bulk_create(entries)
    assert RowHistory.objects.count() == 5

    RowHistoryHandler().delete_entries_older_than(cutoff)

    assert RowHistory.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.row_history
def test_row_history_not_recorded_with_retention_zero_days(settings, data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    model = table.get_model()
    row = model.objects.create()

    # no history will be recorded with zero retention days
    settings.BASEROW_ROW_HISTORY_RETENTION_DAYS = 0
    UpdateRowsActionType.do(
        user,
        table,
        [
            {
                "id": row.id,
                f"field_{name_field.id}": "changed",
            }
        ],
        model,
    )

    assert RowHistory.objects.count() == 0

    # otherwise record row history
    settings.BASEROW_ROW_HISTORY_RETENTION_DAYS = 1
    UpdateRowsActionType.do(
        user,
        table,
        [
            {
                "id": row.id,
                f"field_{name_field.id}": "changed 2",
            }
        ],
        model,
    )

    assert RowHistory.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_insert_entries_in_linked_rows_history(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()
    link_b_to_a = link_a_to_b.link_row_related_field

    row_handler = RowHandler()

    row_b1, row_b2 = row_handler.force_create_rows(
        user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
    ).created_rows
    row_a1 = row_handler.force_create_row(user, table_a, {primary_a.id: "a1"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table_a,
            [
                {"id": row_a1.id, link_a_to_b.db_column: [row_b1.id, row_b2.id]},
            ],
        )
    assert RowHistory.objects.count() == 3

    history_entries = RowHistory.objects.order_by("table_id", "row_id").values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    expected_entries = [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: []},
            "after_values": {link_a_to_b.db_column: [1, 2]},
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a1",
                    "linked_field_id": link_b_to_a.id,
                    "linked_table_id": table_b.id,
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}},
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 2,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}},
                }
            },
        },
    ]

    assert list(history_entries) == expected_entries

    # Now remove one link

    with freeze_time("2021-01-01 12:30"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table_a,
            [
                {"id": row_a1.id, link_a_to_b.db_column: [row_b2.id]},
            ],
        )

    history_entries = RowHistory.objects.order_by(
        "-action_timestamp", "table_id", "row_id"
    ).values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )
    assert RowHistory.objects.count() == 5

    last_entries = list(history_entries)[:2]
    expected_entries = [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 30, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: [1, 2]},
            "after_values": {link_a_to_b.db_column: [2]},
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a1",
                    "linked_field_id": link_b_to_a.id,
                    "linked_table_id": table_b.id,
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 30, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: [1]},
            "after_values": {link_b_to_a.db_column: []},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}},
                }
            },
        },
    ]

    assert last_entries == expected_entries


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_dont_insert_entries_in_linked_rows_history_without_related_field(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(
        user=user, database=database, has_related_field=False
    )
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()

    row_handler = RowHandler()

    row_b1, row_b2 = row_handler.force_create_rows(
        user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
    ).created_rows
    row_a1 = row_handler.force_create_row(user, table_a, {primary_a.id: "a1"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table_a,
            [
                {"id": row_a1.id, link_a_to_b.db_column: [row_b1.id, row_b2.id]},
            ],
        )
    assert RowHistory.objects.count() == 1

    history_entries = RowHistory.objects.values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    expected_entries = [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: []},
            "after_values": {link_a_to_b.db_column: [1, 2]},
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a1",
                    "linked_field_id": None,
                    "linked_table_id": table_b.id,
                }
            },
        }
    ]
    assert list(history_entries) == expected_entries


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_insert_entries_in_linked_rows_history_in_multiple_tables(
    data_fixture,
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    table_c, _, link_c_to_a = data_fixture.create_two_linked_tables(
        user=user, database=database, table_b=table_a
    )
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()
    primary_c = table_c.get_primary_field()
    link_b_to_a = link_a_to_b.link_row_related_field
    link_a_to_c = link_c_to_a.link_row_related_field

    row_handler = RowHandler()

    row_b1, row_b2 = row_handler.force_create_rows(
        user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
    ).created_rows
    row_c1, row_c2 = row_handler.force_create_rows(
        user, table_c, [{primary_c.db_column: "c1"}, {primary_c.db_column: "c2"}]
    ).created_rows
    row_a1, row_a2 = row_handler.force_create_rows(
        user, table_a, [{primary_a.db_column: "a1"}, {primary_a.db_column: "a2"}]
    ).created_rows

    with freeze_time("2021-01-01 12:00"), patch(
        "baserow.contrib.database.rows.signals.rows_history_updated.send"
    ) as mock_signal:
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table_a,
            [
                {
                    "id": row_a1.id,
                    link_a_to_b.db_column: [row_b1.id, row_b2.id],
                    link_a_to_c.db_column: [row_c1.id, row_c2.id],
                },
                {
                    "id": row_a2.id,
                    link_a_to_b.db_column: [row_b1.id, row_b2.id],
                    link_a_to_c.db_column: [row_c1.id, row_c2.id],
                },
            ],
        )

    assert RowHistory.objects.count() == 6

    history_entries = RowHistory.objects.order_by("table_id", "row_id").values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    # Signal should be called once per table with row history entries for that table
    entry_ids = [rhe.id for rhe in RowHistory.objects.order_by("table_id", "row_id")]
    assert mock_signal.call_count == 3

    per_table_args = {}
    for args in mock_signal.call_args_list:
        per_table_args[args[1]["table_id"]] = [
            rhe.id for rhe in args[1]["row_history_entries"]
        ]

    assert len(per_table_args) == 3
    assert len(entry_ids) == 6

    # table_a
    assert table_a.id in per_table_args
    assert per_table_args[table_a.id] == entry_ids[:2]

    # table_b
    assert table_b.id in per_table_args
    assert per_table_args[table_b.id] == entry_ids[2:4]

    # table_c
    assert table_c.id in per_table_args
    assert per_table_args[table_c.id] == entry_ids[4:]

    expected_entries = [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: [], link_a_to_c.db_column: []},
            "after_values": {
                link_a_to_b.db_column: [1, 2],
                link_a_to_c.db_column: [1, 2],
            },
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a1",
                    "linked_field_id": link_b_to_a.id,
                    "linked_table_id": table_b.id,
                },
                link_a_to_c.db_column: {
                    "id": link_a_to_c.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "c1"}, "2": {"value": "c2"}},
                    "primary_value": "a1",
                    "linked_field_id": link_c_to_a.id,
                    "linked_table_id": table_c.id,
                },
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 2,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: [], link_a_to_c.db_column: []},
            "after_values": {
                link_a_to_b.db_column: [1, 2],
                link_a_to_c.db_column: [1, 2],
            },
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a2",
                    "linked_field_id": link_b_to_a.id,
                    "linked_table_id": table_b.id,
                },
                link_a_to_c.db_column: {
                    "id": link_a_to_c.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "c1"}, "2": {"value": "c2"}},
                    "primary_value": "a2",
                    "linked_field_id": link_c_to_a.id,
                    "linked_table_id": table_c.id,
                },
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1, 2]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}, "2": {"value": "a2"}},
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 2,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1, 2]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}, "2": {"value": "a2"}},
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_c.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_c_to_a.db_column: []},
            "after_values": {link_c_to_a.db_column: [1, 2]},
            "fields_metadata": {
                link_c_to_a.db_column: {
                    "id": link_c_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}, "2": {"value": "a2"}},
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_c.id,
            "row_id": 2,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_c_to_a.db_column: []},
            "after_values": {link_c_to_a.db_column: [1, 2]},
            "fields_metadata": {
                link_c_to_a.db_column: {
                    "id": link_c_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}, "2": {"value": "a2"}},
                }
            },
        },
    ]

    assert list(history_entries) == expected_entries


@pytest.mark.django_db
@pytest.mark.row_history
def test_update_rows_insert_entries_in_linked_rows_history_with_values(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(
        user=user, database=database
    )
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()
    link_b_to_a = link_a_to_b.link_row_related_field

    row_handler = RowHandler()

    row_b1, row_b2 = row_handler.force_create_rows(
        user, table_b, [{primary_b.db_column: "b1"}, {primary_b.db_column: "b2"}]
    ).created_rows
    row_a1 = row_handler.force_create_row(user, table_a, {primary_a.id: "a1"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table_a,
            [
                {"id": row_a1.id, link_a_to_b.db_column: ["b1", "b2"]},
            ],
        )
    assert RowHistory.objects.count() == 3

    history_entries = RowHistory.objects.order_by("table_id", "row_id").values(
        "user_id",
        "user_name",
        "table_id",
        "row_id",
        "action_timestamp",
        "action_type",
        "before_values",
        "after_values",
        "fields_metadata",
    )

    expected_entries = [
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_a.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_a_to_b.db_column: []},
            "after_values": {link_a_to_b.db_column: [1, 2]},
            "fields_metadata": {
                link_a_to_b.db_column: {
                    "id": link_a_to_b.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "b1"}, "2": {"value": "b2"}},
                    "primary_value": "a1",
                    "linked_field_id": link_b_to_a.id,
                    "linked_table_id": table_b.id,
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 1,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}},
                }
            },
        },
        {
            "user_id": user.id,
            "user_name": user.first_name,
            "table_id": table_b.id,
            "row_id": 2,
            "action_timestamp": datetime(2021, 1, 1, 12, 0, tzinfo=timezone.utc),
            "action_type": "update_rows",
            "before_values": {link_b_to_a.db_column: []},
            "after_values": {link_b_to_a.db_column: [1]},
            "fields_metadata": {
                link_b_to_a.db_column: {
                    "id": link_b_to_a.id,
                    "type": "link_row",
                    "linked_rows": {"1": {"value": "a1"}},
                }
            },
        },
    ]

    assert list(history_entries) == expected_entries
