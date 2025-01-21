import json
import zipfile

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.import_export.handler import MANIFEST_NAME, ImportExportHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_export_works_with_invalid_simple_formula(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_formula_field(
        user=user,
        table=table,
        formula=f"tonumber(field('{text_field.name}'))",
    )

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "123",
        },
    )

    field_handler = FieldHandler()
    field_handler.delete_field(user, text_field)

    resource = ImportExportHandler().export_workspace_applications(
        applications=[table.database],
        import_export_config=ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=True,
            only_structure=False,
        ),
    )

    file_path = tmpdir.join(
        settings.EXPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        with zip_ref.open(MANIFEST_NAME) as json_file:
            json_data = json.load(json_file)
            database_export = json_data["applications"]["database"]["items"][0]

            db_export_path = database_export["files"]["schema"]
            with zip_ref.open(db_export_path) as db_data_file:
                db_data = json.loads(db_data_file.read())

            assert len(db_data["tables"][0]["rows"]) == 1
            assert text_field.id not in db_data["tables"][0]["rows"][0]
            assert db_data["tables"][0]["rows"][0][f"field_{formula_field.id}"] is None

    tmpdir.mkdir(settings.IMPORT_FILES_DIRECTORY)
    import_file_path = tmpdir.join(
        settings.IMPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    file_path.copy(import_file_path)
    assert import_file_path.isfile()

    ImportExportHandler().import_workspace_applications(
        user=user,
        workspace=workspace,
        resource=resource,
    )


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_export_works_with_invalid_rollup_field(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="primaryfield", table=table, primary=True
    )
    table2_primary_field = data_fixture.create_text_field(
        name="primaryfield", table=table2, primary=True
    )
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    rollup_field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_name=linkrowfield.name,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )

    row_handler = RowHandler()

    table2_row1 = row_handler.create_row(
        user=user,
        table=table2,
        values={
            table2_primary_field.id: "row 2.A",
            rolled_up_field.id: 10,
        },
    )
    table2_row2 = row_handler.create_row(
        user=user,
        table=table2,
        values={
            table2_primary_field.id: "row 2.B",
            rolled_up_field.id: 20,
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            table_primary_field.id: "row 1.A",
            linkrowfield.id: [table2_row1.id, table2_row2.id],
        },
    )

    table_handler = TableHandler()
    table_handler.delete_table(user, table2)

    rollup_field.refresh_from_db()
    assert rollup_field.formula_type == "invalid"

    resource = ImportExportHandler().export_workspace_applications(
        applications=[table.database],
        import_export_config=ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=True,
            only_structure=False,
        ),
    )

    file_path = tmpdir.join(
        settings.EXPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        with zip_ref.open(MANIFEST_NAME) as json_file:
            json_data = json.load(json_file)
            database_export = json_data["applications"]["database"]["items"][0]

            db_export_path = database_export["files"]["schema"]
            with zip_ref.open(db_export_path) as db_data_file:
                db_data = json.loads(db_data_file.read())
                assert (
                    "references the deleted or unknown field"
                    in db_data["tables"][0]["fields"][1]["error"]
                )

    tmpdir.mkdir(settings.IMPORT_FILES_DIRECTORY)
    import_file_path = tmpdir.join(
        settings.IMPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    file_path.copy(import_file_path)
    assert import_file_path.isfile()

    ImportExportHandler().import_workspace_applications(
        user=user,
        workspace=workspace,
        resource=resource,
    )
