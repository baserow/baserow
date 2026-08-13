import re
from importlib import import_module
from unittest.mock import patch

from django.db import connection, transaction

import pytest
from pyinstrument import Profiler

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableUsageHandler
from baserow.contrib.database.table.usage_types import (
    TableWorkspaceStorageUsageItemType,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.usage.registries import USAGE_UNIT_MB
from baserow.test_utils.setup_formulas import iter_formula_pgsql_functions

RICH_TEXT_FILE_UNIQUES_FUNC = import_module(
    "baserow.contrib.database.migrations.0224_rich_text_file_uniques"
).RICH_TEXT_FILE_UNIQUES_FUNC

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.table.tasks.update_table_usage.delay",
)


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_item_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)

    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_megabytes = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_megabytes == 0

    user_file_1 = data_fixture.create_user_file(
        original_name="test.png", is_image=True, size=2.5 * USAGE_UNIT_MB
    )

    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_1.name}]})

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_megabytes = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_megabytes == 2

    user_file_2 = data_fixture.create_user_file(
        original_name="another_file", is_image=True, size=7.5 * USAGE_UNIT_MB
    )

    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_2.name}]})

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_megabytes = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_megabytes == 10


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_item_type_trashed_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)
    user_file_1 = data_fixture.create_user_file(
        original_name="test.png", is_image=True, size=1 * USAGE_UNIT_MB
    )

    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_1.name}]})

    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 1

    TrashHandler().trash(user, workspace, database, table)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0

    TrashHandler.restore_item(user, "table", table.id)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 1


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_item_type_trashed_file_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)
    user_file_1 = data_fixture.create_user_file(
        original_name="test.png", is_image=True, size=1 * USAGE_UNIT_MB
    )

    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_1.name}]})

    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 1

    FieldHandler().delete_field(user, file_field)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0

    TrashHandler.restore_item(user, "field", file_field.id)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 1


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_item_type_trashed_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)
    user_file_1 = data_fixture.create_user_file(
        original_name="test.png", is_image=True, size=5 * USAGE_UNIT_MB
    )

    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_1.name}]})

    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 5

    TrashHandler().trash(user, workspace, database, database)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0

    TrashHandler.restore_item(user, "application", database.id)
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 5


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_item_type_unique_files(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    table_2 = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)
    file_field_2 = data_fixture.create_file_field(table=table)
    file_field_table_2 = data_fixture.create_file_field(table=table_2)

    user_file_1 = data_fixture.create_user_file(
        original_name="test.png", is_image=True, size=1 * USAGE_UNIT_MB
    )
    user_file_2 = data_fixture.create_user_file(
        original_name="test2.png", is_image=True, size=2 * USAGE_UNIT_MB
    )

    RowHandler().create_row(
        user,
        table,
        {file_field.id: [{"name": user_file_1.name}, {"name": user_file_1.name}]},
    )

    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_USAGE_UNIT_MB = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_USAGE_UNIT_MB == 1

    # The same file in the same field is counted once
    RowHandler().create_row(user, table, {file_field.id: [{"name": user_file_1.name}]})

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_USAGE_UNIT_MB = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_USAGE_UNIT_MB == 1

    # The same file in another field of the same table is also counted once
    row = RowHandler().create_row(
        user, table, {file_field_2.id: [{"name": user_file_1.name}]}
    )

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_USAGE_UNIT_MB = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_USAGE_UNIT_MB == 1

    # Updating a file field will trigger a recalculation
    RowHandler().update_row(
        user, table, row, {file_field_2.id: [{"name": user_file_2.name}]}
    )

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_USAGE_UNIT_MB = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_USAGE_UNIT_MB == 3

    # The same file in a different table is counted as a new file
    RowHandler().create_row(
        user, table_2, {file_field_table_2.id: [{"name": user_file_1.name}]}
    )

    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage_in_USAGE_UNIT_MB = (
        table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_USAGE_UNIT_MB == 3 + 1


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_includes_rich_text_images(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    rich_text_field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )

    user_file = data_fixture.create_user_file(
        original_name="photo.png", is_image=True, size=3 * USAGE_UNIT_MB
    )

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{rich_text_field.id}": f"![photo][{user_file.name}]",
            "order": 1,
        }
    )

    with connection.cursor() as cur:
        cur.execute(
            "SELECT * FROM _get_baserow_table_rich_text_file_uniques(%s)",
            [table.id],
        )
        rt_results = cur.fetchall()

    assert len(rt_results) == 1
    assert rt_results[0][0] == user_file.unique

    # Drive the real entry point too: the inner function returning the right row
    # means nothing if the deduplicating wrapper does not union it in.
    TableUsageHandler.mark_table_for_usage_update(table.id)
    TableUsageHandler.update_tables_usage()

    assert (
        TableWorkspaceStorageUsageItemType().calculate_storage_usage_workspace(
            workspace.id
        )
        == 3
    )


@pytest.mark.django_db(transaction=True)
def test_table_workspace_storage_usage_deduplicates_rich_text_and_file_field(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)
    rich_text_field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )

    user_file = data_fixture.create_user_file(
        original_name="photo.png", is_image=True, size=5 * USAGE_UNIT_MB
    )

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{file_field.id}": [{"name": user_file.name}],
            f"field_{rich_text_field.id}": f"![photo][{user_file.name}]",
            "order": 1,
        }
    )

    with connection.cursor() as cur:
        cur.execute(
            "SELECT * FROM _get_baserow_table_file_uniques(%s)",
            [table.id],
        )
        ff_results = cur.fetchall()
        cur.execute(
            "SELECT * FROM _get_baserow_table_rich_text_file_uniques(%s)",
            [table.id],
        )
        rt_results = cur.fetchall()

    ff_uniques = {r[0] for r in ff_results}
    rt_uniques = {r[0] for r in rt_results}

    assert user_file.unique in ff_uniques
    assert user_file.unique in rt_uniques
    assert ff_uniques == rt_uniques

    # The same file referenced from both fields must be billed once, not twice.
    TableUsageHandler.mark_table_for_usage_update(table.id)
    TableUsageHandler.update_tables_usage()

    assert (
        TableWorkspaceStorageUsageItemType().calculate_storage_usage_workspace(
            workspace.id
        )
        == 5
    )


@pytest.mark.django_db
def test_distinct_file_uniques_wrapper_includes_rich_text(data_fixture):
    """The deduplicating wrapper must return the rich text image's unique."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(original_name="z.png", is_image=True)
    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": f"![a][{user_file.name}]"})

    with connection.cursor() as cur:
        cur.execute("SELECT get_distinct_baserow_table_file_uniques(%s)", [table.id])
        result = cur.fetchone()[0]

    assert result is not None, (
        "get_distinct_baserow_table_file_uniques returned NULL; its "
        "EXCEPTION WHEN OTHERS handler is masking a failure"
    )
    assert user_file.unique in result


@pytest.mark.django_db(transaction=True)
def test_distinct_file_uniques_wrapper_tolerates_a_broken_inner_function(data_fixture):
    """The wrapper must survive a failing inner function.

    Usage is computed by a bulk job over every table, so one unreadable table has
    to degrade to null rather than abort the run. The handler is narrowed
    to specific codes, but the catch-all must still return null (while warning) so
    this contract holds for unexpected errors too.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, long_text_enable_rich_text=True
    )
    user_file = data_fixture.create_user_file(original_name="z.png", is_image=True)
    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": f"![a][{user_file.name}]"})

    with connection.cursor() as cur:
        # Replace the rich text helper with one that raises an error the handler
        # does not name explicitly, to exercise the WHEN OTHERS branch.
        cur.execute(
            """
            CREATE OR REPLACE FUNCTION _get_baserow_table_rich_text_file_uniques(
                table__id INT
            )
            RETURNS TABLE(file_unique TEXT, field_id INT, table_id INT) AS $$
            BEGIN
                RAISE division_by_zero;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        try:
            cur.execute(
                "SELECT get_distinct_baserow_table_file_uniques(%s)", [table.id]
            )
            result = cur.fetchone()[0]
        finally:
            cur.execute(RICH_TEXT_FILE_UNIQUES_FUNC)

    assert result is None

    # And the real function must be back in place for any later query.
    with connection.cursor() as cur:
        cur.execute("SELECT get_distinct_baserow_table_file_uniques(%s)", [table.id])
        assert user_file.unique in cur.fetchone()[0]


def test_migration_0224_does_not_export_its_rollback_function_to_the_test_harness():
    """setup_formulas scrapes the pgSQL function definitions out of the migration
    files by regex and installs them in file order. Migration 0224 also holds the
    rollback definition of the wrapper, so if it is scraped it is installed last
    and silently replaces the new UNION version in every test database."""

    last_by_name = {}
    for func in iter_formula_pgsql_functions():
        match = re.search(
            r"create or replace function\s+([a-zA-Z0-9_]+)", func, re.IGNORECASE
        )
        if match:
            last_by_name[match.group(1)] = func

    winner = last_by_name.get("get_distinct_baserow_table_file_uniques", "")
    assert "_get_baserow_table_rich_text_file_uniques" in winner, (
        "the last installed definition of get_distinct_baserow_table_file_uniques "
        "does not reference the rich text function - the rollback constant in "
        "migration 0224 wins"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_table_workspace_storage_usage_item_type_performance(data_fixture):
    files_amount = 5000
    file_size_each_in_USAGE_UNIT_MB = 2

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    file_field = data_fixture.create_file_field(table=table)

    user_files = [
        {
            f"field_{file_field.id}": [
                {
                    "name": data_fixture.create_user_file(
                        is_image=True,
                        size=file_size_each_in_USAGE_UNIT_MB * USAGE_UNIT_MB,
                        uploaded_by=user,
                    ).name
                }
            ]
        }
        for _ in range(files_amount)
    ]

    RowHandler().create_rows(user, table, user_files)

    profiler = Profiler()
    profiler.start()
    table_workspace_storage_usage_item_type = TableWorkspaceStorageUsageItemType()
    table_workspace_storage_usage_item_type.calculate_storage_usage_instance()
    usage = table_workspace_storage_usage_item_type.calculate_storage_usage_workspace(
        workspace.id
    )
    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))

    assert usage == files_amount * file_size_each_in_USAGE_UNIT_MB


@pytest.mark.django_db(transaction=True)
def test_toggling_rich_text_schedules_a_usage_recalculation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=False
    )

    # Turning rich text on moves the field into the storage usage query without
    # touching a single row, so the update has to schedule the recalculation.
    with patch(
        "baserow.contrib.database.table.tasks.update_table_usage.delay"
    ) as mock_delay:
        with transaction.atomic():
            FieldHandler().update_field(user, field, long_text_enable_rich_text=True)
        mock_delay.assert_called_with(table.id)

    # Turning it back off has to as well: the old field still carries files.
    field.refresh_from_db()
    with patch(
        "baserow.contrib.database.table.tasks.update_table_usage.delay"
    ) as mock_delay:
        with transaction.atomic():
            FieldHandler().update_field(user, field, long_text_enable_rich_text=False)
        mock_delay.assert_called_with(table.id)


@pytest.mark.django_db(transaction=True)
def test_updating_a_plain_field_does_not_schedule_a_usage_recalculation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Text")

    with patch(
        "baserow.contrib.database.table.tasks.update_table_usage.delay"
    ) as mock_delay:
        with transaction.atomic():
            FieldHandler().update_field(user, field, name="Renamed")

    mock_delay.assert_not_called()
