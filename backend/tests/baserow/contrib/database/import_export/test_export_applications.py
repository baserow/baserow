import json
import zipfile

from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.import_export.handler import (
    EXPORT_FORMAT_VERSION,
    MANIFEST_NAME,
    SIGNATURE_NAME,
    ImportExportHandler,
)
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage
from baserow.core.user_files.models import UserFile
from baserow.test_utils.helpers import setup_interesting_test_database


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_interesting_database(
    data_fixture, api_client, tmpdir, settings, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database_name = "To be exported"

    cli_import_export_config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=False
    )

    data_fixture.create_import_export_trusted_source()

    database = setup_interesting_test_database(
        data_fixture,
        user=user,
        workspace=workspace,
        name=database_name,
    )

    storage = get_default_storage()
    for user_file in UserFile.objects.all():
        data_fixture.save_content_in_user_file(user_file=user_file, storage=storage)

    resource = ImportExportHandler().export_workspace_applications(
        applications=[database],
        import_export_config=cli_import_export_config,
        storage=storage,
        progress_builder=None,
    )

    file_path = tmpdir.join(
        settings.EXPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    assert file_path.isfile()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        assert MANIFEST_NAME in zip_ref.namelist()
        assert SIGNATURE_NAME in zip_ref.namelist()

        with zip_ref.open(MANIFEST_NAME) as json_file:
            json_data = json.load(json_file)
            assert json_data["version"] == EXPORT_FORMAT_VERSION
            assert json_data["configuration"] == {"only_structure": False}
            assert json_data["total_files"] == 12
            assert len(json_data["checksums"].keys()) == 10
            assert len(json_data["applications"]["database"]["items"]) == 1

            assert (
                json_data["applications"]["database"]["version"]
                == EXPORT_FORMAT_VERSION
            )
            assert json_data["applications"]["database"]["configuration"] == {}
            exported_database = json_data["applications"]["database"]["items"][0]
            assert exported_database["id"] == database.id
            assert exported_database["type"] == "database"
            assert exported_database["name"] == database_name
            assert exported_database["files"]["schema"] is not None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_workspace_writes_file_to_storage(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    field_name = f"field_{text_field.id}"

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #2",
        },
    )

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

            assert database_export["name"] == table.database.name
            assert database_export["total_files"] == 1

            db_export_path = database_export["files"]["schema"]
            with zip_ref.open(db_export_path) as db_data_file:
                db_data = json.loads(db_data_file.read())

            assert db_data["name"] == table.database.name
            assert len(db_data["tables"]) == 1

            assert db_data["tables"][0]["name"] == table.name
            assert len(db_data["tables"][0]["rows"]) == 2
            assert db_data["tables"][0]["rows"][0][field_name] == "row #1"
            assert db_data["tables"][0]["rows"][0][field_name] == "row #1"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exporting_only_structure_writes_file_to_storage(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #2",
        },
    )

    resource = ImportExportHandler().export_workspace_applications(
        applications=[table.database],
        import_export_config=ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=True,
            only_structure=True,
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

            assert database_export["name"] == table.database.name
            assert database_export["total_files"] == 1
            assert "media" not in database_export["files"]

            db_export_path = database_export["files"]["schema"]
            with zip_ref.open(db_export_path) as db_data_file:
                db_data = json.loads(db_data_file.read())

            assert db_data["name"] == table.database.name
            assert len(db_data["tables"]) == 1

            assert db_data["tables"][0]["name"] == table.name
            assert len(db_data["tables"][0]["rows"]) == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_exported_files_checksum(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #2",
        },
    )

    resource = ImportExportHandler().export_workspace_applications(
        applications=[table.database],
        import_export_config=ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=True,
            only_structure=True,
        ),
    )

    file_path = tmpdir.join(
        settings.EXPORT_FILES_DIRECTORY, resource.get_archive_name()
    )
    assert file_path.isfile()

    storage = get_default_storage()
    path = ImportExportHandler().get_import_storage_path(resource.uuid.hex)

    handler = ImportExportHandler()

    with zipfile.ZipFile(file_path, "r") as zip_ref:
        manifest_data = handler.validate_manifest(zip_ref)
        handler.extract_files_from_zip(path, zip_ref, storage)
        checksums = manifest_data["checksums"]
        db_files = manifest_data["applications"]["database"]["items"][0]["files"]
        database_file = db_files["schema"]
        database_file_checksum = checksums[database_file]

        file_path = handler.get_import_storage_path(resource.uuid.hex, database_file)

        calculated_checksum = handler.compute_checksum_from_file(file_path, storage)
        assert database_file_checksum == calculated_checksum


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_IMPORT_EXPORT_TABLE_ROWS_COUNT_LIMIT=1)
def test_export_with_rows_limit(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)

    row_handler = RowHandler()
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        values={
            text_field.id: "row #2",
        },
    )

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


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_export_works_with_invalid_formula(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
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


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_export_works_with_invalid_rollup_field(
    data_fixture,
    api_client,
    tmpdir,
    settings,
    use_tmp_media_root,
):
    user, token = data_fixture.create_user_and_token()
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
