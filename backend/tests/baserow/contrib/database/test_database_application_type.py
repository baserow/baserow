import os
from datetime import datetime, timezone
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage

import pytest
from freezegun import freeze_time

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.models import FormulaField, TextField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import CreateApplicationActionType
from baserow.core.handler import CoreHandler
from baserow.core.models import Template
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress
from baserow.test_utils.helpers import setup_interesting_test_database


@pytest.mark.django_db
def test_import_export_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    workspace_user = data_fixture.create_user_workspace(workspace=workspace, user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    text_field = data_fixture.create_text_field(table=table, name="text")
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula",
        formula=f"field('{text_field.name}')",
        formula_type="text",
    )
    data_fixture.create_link_row_field(table=table, link_row_table=table)
    view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(view=view, field=text_field, value="Test")
    data_fixture.create_view_sort(view=view, field=text_field)

    with freeze_time("2021-01-01 12:30"):
        row = (
            RowHandler()
            .force_create_rows(
                user,
                table,
                [
                    {f"field_{text_field.id}": "Test"},
                    {f"field_{text_field.id}": "Test 2"},
                ],
            )
            .created_rows[0]
        )

    with freeze_time("2021-01-02 13:30"):
        row = (
            RowHandler()
            .force_update_rows(
                user, table, [{"id": row.id, f"field_{text_field.id}": "Test"}]
            )
            .updated_rows[0]
        )

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    # Delete the updated on, because the import should also be compatible with
    # without these values present.
    del serialized["tables"][0]["rows"][1]["created_on"]
    del serialized["tables"][0]["rows"][1]["updated_on"]

    imported_workspace = data_fixture.create_workspace()
    imported_workspace_user = data_fixture.create_user_workspace(
        workspace=imported_workspace, user=user
    )
    id_mapping = {}

    with freeze_time("2022-01-01 12:00"):
        imported_database = database_type.import_serialized(
            imported_workspace,
            serialized,
            config,
            id_mapping,
            None,
            None,
        )

    assert imported_database.id != database.id
    assert imported_database.workspace_id == imported_workspace.id
    assert imported_database.name == database.name
    assert imported_database.order == database.order
    assert imported_database.table_set.all().count() == 1

    imported_table = imported_database.table_set.all().first()
    assert imported_table.id != table.id
    assert imported_table.name == table.name
    assert imported_table.order == table.order
    assert imported_table.field_set.all().count() == 3
    assert imported_table.view_set.all().count() == 1

    imported_view = imported_table.view_set.all().first()
    assert imported_view.viewfilter_set.all().count() == 1
    assert imported_view.viewsort_set.all().count() == 1

    imported_model = imported_table.get_model()
    assert imported_model.objects.all().count() == 2
    imported_row = imported_model.objects.all().first()
    imported_row_2 = imported_model.objects.all().last()

    imported_text_field = TextField.objects.get(table=imported_table)
    imported_formula_field = FormulaField.objects.get(table=imported_table)
    assert imported_formula_field.formula == f"field('{imported_text_field.name}')"

    # Because the rows have unique id within the table, we expect the row id to be the
    # same.
    assert imported_row.id == row.id
    assert imported_row.order == row.order
    assert imported_row.created_on == datetime(2021, 1, 1, 12, 30, tzinfo=timezone.utc)
    assert imported_row.updated_on == datetime(2021, 1, 2, 13, 30, tzinfo=timezone.utc)
    assert imported_row.last_modified_by == row.last_modified_by
    assert getattr(
        imported_row, f'field_{id_mapping["database_fields"][text_field.id]}'
    ) == (getattr(row, f"field_{text_field.id}"))
    assert (
        imported_formula_field.internal_formula == f"error_to_null(field('"
        f"{imported_text_field.db_column}'))"
    )
    assert imported_formula_field.formula_type == "text"
    assert getattr(
        imported_row, f'field_{id_mapping["database_fields"][formula_field.id]}'
    ) == (getattr(row, f"field_{formula_field.id}"))

    # Because the created on and updated on were not provided, we expect these values
    # to be equal to "now", which was frozen by freezegun during the import.
    assert imported_row_2.created_on == datetime(2022, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert imported_row_2.updated_on == datetime(2022, 1, 1, 12, 0, tzinfo=timezone.utc)

    # It must still be possible to create a new row in the imported table
    row_3 = imported_model.objects.create()
    assert row_3.id == 3


@pytest.mark.django_db
def test_create_application_and_init_with_data(data_fixture):
    core_handler = CoreHandler()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database_1 = core_handler.create_application(
        user, workspace, "database", name="Database 1"
    )
    assert Table.objects.filter(database=database_1).count() == 0

    database_2 = core_handler.create_application(
        user, workspace, "database", True, name="Database 2"
    )
    assert Table.objects.filter(database=database_2).count() == 1


@pytest.mark.django_db
@patch("baserow.core.signals.application_created.send")
def test_install_template_sets_last_modified_by_none(
    send_mock, tmpdir, data_fixture, settings
):
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    handler = CoreHandler()
    handler.sync_templates(storage=storage)

    template = Template.objects.get(slug="example-template")
    applications, id_mapping = handler.install_template(
        user, workspace, template, storage=storage
    )

    assert len(applications) == 1
    assert applications[0].workspace_id == workspace.id
    assert applications[0].name == "Event marketing"

    template_tables = TableHandler().list_workspace_tables(
        workspace=workspace, user=user
    )
    template_example_table = template_tables[0]
    table_model = template_example_table.get_model()
    assert table_model.objects.all()[0].last_modified_by is None
    assert table_model.objects.all()[1].last_modified_by is None


@pytest.mark.django_db
def test_database_application_creation_does_register_an_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    assert Action.objects.count() == 0
    action_type_registry.get_by_type(CreateApplicationActionType).do(
        user,
        workspace,
        DatabaseApplicationType.type,
        name="Actions please",
        init_with_data=False,
    )
    assert Action.objects.count() == 1


@pytest.mark.django_db
def test_perform_create_interesting_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = setup_interesting_test_database(
        data_fixture, user=user, workspace=workspace, name="db"
    )
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=database,
        name="snapshot",
        created_by=user,
    )
    progress = Progress(total=100)

    SnapshotHandler().perform_create(snapshot, progress)

    snapshot.refresh_from_db()
    for table_name in ["A", "B", "C"]:
        snapshotted_table = Table.objects.get(
            database=snapshot.snapshot_to_application, name=table_name
        )
        model = snapshotted_table.get_model()
        assert model.objects.count() == 2

    assert progress.progress == 100


@pytest.mark.django_db
def test_perform_restore_interesting_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace, order=1)

    database = setup_interesting_test_database(
        data_fixture, user=user, workspace=workspace, name="db"
    )
    database.workspace = None
    database.save(update_fields=["workspace"])

    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application,
        snapshot_to_application=database,
        name="snapshot",
        created_by=user,
    )
    progress = Progress(total=100)

    restored = SnapshotHandler().perform_restore(snapshot, progress)
    snapshot.refresh_from_db()
    for table_name in ["A", "B", "C"]:
        snapshotted_table = Table.objects.get(database=restored, name=table_name)
        model = snapshotted_table.get_model()
        assert model.objects.count() == 2
    assert progress.progress == 100
