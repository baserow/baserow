import pytest
from pyinstrument import Profiler

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.usage_types import (
    TableWorkspaceStorageUsageItemType,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.usage.registries import USAGE_UNIT_MB

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
