from django.db import connection

import pytest
from psycopg2 import sql

from baserow.contrib.database.rows.handler import RowHandler


# @pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_migration_rows_with_deleted_singleselect_options(
    data_fixture, migrator, teardown_table_metadata
):
    migrate_from = [
        ("database", "0175_formviewfieldoptions_include_all_select_options_and_more"),
    ]
    migrate_to = [("database", "0176_remove_singleselect_missing_options")]

    migrator.migrate(migrate_from)

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, user=user)

    # Test that it doesn't crash on larger dataset
    row_handler = RowHandler()

    table_for_values = data_fixture.create_database_table(
        database=database, name=f"Table for values"
    )
    text_field_for_values = data_fixture.create_text_field(
        table=table_for_values, name="text_field", order=0
    )
    option_field_for_values = data_fixture.create_single_select_field(
        table=table_for_values, name="option_field", order=1
    )

    option_a = data_fixture.create_select_option(
        field=option_field_for_values, value=f"Option A"
    )
    option_b = data_fixture.create_select_option(
        field=option_field_for_values, value=f"Option B"
    )
    option_c = data_fixture.create_select_option(
        field=option_field_for_values, value=f"Option C"
    )
    rows = [
        {
            text_field_for_values.db_column: f"Row #1",
            option_field_for_values.db_column: option_a.id,
        },
        {
            text_field_for_values.db_column: f"Row #2",
            option_field_for_values.db_column: option_b.id,
        },
        {
            text_field_for_values.db_column: f"Row #3",
            option_field_for_values.db_column: option_c.id,
        },
        {
            text_field_for_values.db_column: f"Row #4",
            option_field_for_values.db_column: option_b.id,
        },
    ]

    row_handler.create_rows(user=user, table=table_for_values, rows_values=rows)

    option_b.delete()

    # Update Row #4 to contain option value that does not exist
    with connection.cursor() as cursor:
        result = cursor.execute(
            sql.SQL(
                "UPDATE {table} SET {field} = 8 WHERE {text_field} = 'Row #4'"
            ).format(
                table=sql.Identifier(
                    f"database_table_{option_field_for_values.table.id}"
                ),
                field=sql.Identifier(f"field_{option_field_for_values.id}"),
                text_field=sql.Identifier(f"field_{text_field_for_values.id}"),
            )
        )

    # Row is properly updated
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SELECT {text_field}, {option_field} FROM {table} WHERE {text_field} = 'Row #4'"
            ).format(
                table=sql.Identifier(
                    f"database_table_{option_field_for_values.table.id}"
                ),
                text_field=sql.Identifier(f"field_{text_field_for_values.id}"),
                option_field=sql.Identifier(f"field_{option_field_for_values.id}"),
            )
        )
        rows_from_db = cursor.fetchall()
    assert len(rows_from_db) == 1
    assert rows_from_db[0] == ("Row #4", 8)

    migrator.migrate(migrate_to)

    # After migration, the row is updated to contain None
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SELECT {text_field}, {option_field} FROM {table} WHERE {text_field} = 'Row #4'"
            ).format(
                table=sql.Identifier(
                    f"database_table_{option_field_for_values.table.id}"
                ),
                text_field=sql.Identifier(f"field_{text_field_for_values.id}"),
                option_field=sql.Identifier(f"field_{option_field_for_values.id}"),
            )
        )
        rows_from_db = cursor.fetchall()

    assert len(rows_from_db) == 1
    assert rows_from_db[0] == ("Row #4", None)
