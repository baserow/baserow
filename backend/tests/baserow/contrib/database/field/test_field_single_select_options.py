from unittest.mock import patch

from django.db import connection
from django.test import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.psycopg import sql


# @pytest.mark.disabled_in_ci  # Disable this test in CI in next release.
@pytest.mark.django_db
@override_settings(BASEROW_DISABLE_MODEL_CACHE=True)
@pytest.mark.skip(
    "Fails because it uses the latest version of the models instead of the ones at the "
    "time of the migration"
)
def test_migration_rows_with_deleted_singleselect_options(
    data_fixture, migrator, teardown_table_metadata
):
    migrate_from = [
        ("database", "0175_formviewfieldoptions_include_all_select_options_and_more"),
    ]
    migrate_to = [("database", "0178_remove_singleselect_missing_options")]

    migrator.migrate(migrate_from)

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    single_select_field = data_fixture.create_single_select_field(table=table)

    option_a = data_fixture.create_select_option(
        field=single_select_field, value=f"Option A"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value=f"Option B"
    )

    row_with_b = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {single_select_field.db_column: opt.id} for opt in (option_a, option_b)
            ],
        )
        .created_rows[1]
    )

    single_select_field_type = field_type_registry.get_by_model(single_select_field)

    # Temporarily mock, as before the MR that introduced the migration
    with patch.object(
        single_select_field_type, "before_field_options_update", return_value=None
    ):
        FieldHandler().update_field(
            user,
            single_select_field,
            select_options=[
                {
                    "id": option_a.id,
                    "value": "A",
                    "color": "blue",
                }
            ],
        )

    def check_row_b_option_id():
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT {option_field} FROM {table} WHERE id = %s").format(
                    table=sql.Identifier(f"database_table_{table.id}"),
                    option_field=sql.Identifier(single_select_field.db_column),
                ),
                [row_with_b.id],
            )
            return cursor.fetchall()

    assert check_row_b_option_id() == [(option_b.id,)]

    # the migration should remove all the deleted options ids
    migrator.migrate(migrate_to)

    assert check_row_b_option_id() == [(None,)]


@pytest.mark.django_db
def test_single_select_ids_are_removed_from_rows_when_deleted(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    single_select_field = data_fixture.create_single_select_field(table=table)

    option_a = data_fixture.create_select_option(field=single_select_field, value=f"A")
    option_b = data_fixture.create_select_option(field=single_select_field, value=f"B")

    row_with_b = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {single_select_field.db_column: opt.id} for opt in (option_a, option_b)
            ],
        )
        .created_rows[1]
    )

    # Keep only A, and remove B
    FieldHandler().update_field(
        user,
        single_select_field,
        select_options=[
            {
                "id": option_a.id,
                "value": "A",
                "color": "blue",
            }
        ],
    )

    def check_row_b_option_id():
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT {option_field} FROM {table} WHERE id = %s").format(
                    table=sql.Identifier(f"database_table_{table.id}"),
                    option_field=sql.Identifier(single_select_field.db_column),
                ),
                [row_with_b.id],
            )
            return cursor.fetchall()

    assert check_row_b_option_id() == [(None,)]


@pytest.mark.django_db
def test_single_select_field_default_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    single_select_field = data_fixture.create_single_select_field(
        table=table, name="Status"
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="B", color="red"
    )

    row_handler = RowHandler()

    # Without a default value, new rows should have null for the single select
    row_1 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_2 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{single_select_field.id}": option_b.id},
    )
    assert getattr(row_1, f"field_{single_select_field.id}") is None
    assert getattr(row_2, f"field_{single_select_field.id}").id == option_b.id

    # Set option A as default
    field_handler = FieldHandler()
    single_select_field = field_handler.update_field(
        user=user, field=single_select_field, single_select_default=option_a.id
    )

    row_3 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    row_4 = row_handler.force_create_row(
        user=user,
        table=table,
        values={f"field_{single_select_field.id}": option_b.id},
    )
    assert getattr(row_3, f"field_{single_select_field.id}").id == option_a.id
    assert getattr(row_4, f"field_{single_select_field.id}").id == option_b.id

    # Remove the default value
    single_select_field = field_handler.update_field(
        user=user, field=single_select_field, single_select_default=None
    )

    row_5 = row_handler.force_create_row(
        user=user,
        table=table,
    )
    assert getattr(row_5, f"field_{single_select_field.id}") is None

    # Existing rows should keep their values after default value changes
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    row_4.refresh_from_db()
    row_5.refresh_from_db()

    assert getattr(row_1, f"field_{single_select_field.id}") is None
    assert getattr(row_2, f"field_{single_select_field.id}").id == option_b.id
    assert getattr(row_3, f"field_{single_select_field.id}").id == option_a.id
    assert getattr(row_4, f"field_{single_select_field.id}").id == option_b.id
    assert getattr(row_5, f"field_{single_select_field.id}") is None
