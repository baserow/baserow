from io import BytesIO
from typing import Callable
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.db import transaction

import pytest
from PIL import Image

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import LongTextField, RollupField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.rich_text_utils import extract_user_file_names
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile
from baserow.test_utils.fixtures import Fixtures


@pytest.mark.import_export_workspace
@pytest.mark.django_db()
def test_import_export_works_with_invalid_rollup_field(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    rollup_field = FieldHandler().create_field(
        user,
        table_a,
        "rollup",
        name="rollup_field",
        through_field_name=link_a_to_b.name,
        target_field_id=table_b.get_primary_field().id,
        rollup_function="min",
    )

    TableHandler().delete_table(user, table_b)
    rollup_field.refresh_from_db()
    assert rollup_field.formula_type == "invalid"

    import_export_config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=True
    )
    exported_db = DatabaseApplicationType().export_serialized(
        table_a.database, import_export_config
    )

    assert (
        "references the deleted or unknown field"
        in exported_db["tables"][0]["fields"][1]["error"]
    )

    imported_app = DatabaseApplicationType().import_serialized(
        table_a.database.workspace, exported_db, import_export_config, {}
    )

    imported_field = RollupField.objects.get(table=imported_app.table_set.first())
    assert imported_field.formula_type == "invalid"
    assert "references the deleted or unknown field" in imported_field.error


def _png_bytes(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _create_rich_text_rows_with_images(
    data_fixture: Fixtures, user: AbstractUser
) -> tuple[Table, LongTextField, list[UserFile]]:
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    red, blue = (
        UserFileHandler().upload_user_file(
            user, f"{color}.png", BytesIO(_png_bytes(color))
        )
        for color in ("red", "blue")
    )
    # Mention notifications use select_for_update, which fails in autocommit mode.
    with transaction.atomic():
        RowHandler().create_rows(
            user,
            table,
            [
                {field.db_column: f"intro ![a][{red.name}] and ![b][{blue.name}]"},
                {
                    field.db_column: f"![c][{blue.name}] twice ![d][{blue.name}]\n\n"
                    f"- item ![a][{red.name}]"
                },
            ],
        )
    return table, field, [red, blue]


def _rich_text_values(table: Table, field: LongTextField) -> list[str]:
    return list(
        table.get_model().objects.order_by("id").values_list(field.db_column, flat=True)
    )


def _rename_references(value: str, new_name_by_old: dict[str, str]) -> str:
    for old_name, new_name in new_name_by_old.items():
        value = value.replace(old_name, new_name)
    return value


def _assert_values_pass_write_validation(
    field: LongTextField, values: list[str]
) -> None:
    field_type = field_type_registry.get_by_model(field)
    for value in values:
        assert field_type.prepare_value_for_db(field, value) == value


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_workspace_export_import_restores_rich_text_images(
    data_fixture, use_tmp_media_root
):
    exporter = data_fixture.create_user()
    table, field, user_files = _create_rich_text_rows_with_images(
        data_fixture, exporter
    )
    original_values = _rich_text_values(table, field)
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    user_file_handler = UserFileHandler()
    storage = get_default_storage()

    resource = handler.export_workspace_applications(
        applications=[table.database],
        import_export_config=ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )

    export_path = handler.get_export_storage_path(resource.get_archive_name())
    with storage.open(export_path, "rb") as archive, ZipFile(archive) as zip_file:
        archived_names = zip_file.namelist()
    image_names = [user_file.name for user_file in user_files]
    assert [archived_names.count(name) for name in image_names] == [1, 1]

    original_bytes_by_hash = {}
    for user_file in user_files:
        path = user_file_handler.user_file_path(user_file)
        with storage.open(path, "rb") as stored_file:
            original_bytes_by_hash[user_file.sha256_hash] = stored_file.read()
        # Without the originals the import can only restore images from the archive.
        storage.delete(path)
        user_file.delete()

    importer = data_fixture.create_user()
    target_workspace = data_fixture.create_workspace(user=importer)
    with storage.open(export_path, "rb") as archive:
        import_resource = handler.create_resource_from_file(
            importer, "export.zip", archive
        )
    [imported_database] = handler.import_workspace_applications(
        importer, target_workspace, import_resource
    )

    imported_table = Table.objects.get(database=imported_database)
    imported_field = imported_table.field_set.get(name=field.name).specific
    imported_values = _rich_text_values(imported_table, imported_field)
    imported_names = set().union(*map(extract_user_file_names, imported_values))
    imported_name_by_hash = {}
    for name in imported_names:
        imported_file = UserFile.objects.get(
            unique=UserFile.deconstruct_name(name)["unique"]
        )
        assert imported_file.name == name
        with storage.open(user_file_handler.user_file_path(name), "rb") as restored:
            assert restored.read() == original_bytes_by_hash[imported_file.sha256_hash]
        imported_name_by_hash[imported_file.sha256_hash] = name

    assert imported_name_by_hash.keys() == original_bytes_by_hash.keys()
    new_name_by_old = {
        user_file.name: imported_name_by_hash[user_file.sha256_hash]
        for user_file in user_files
    }
    assert imported_values == [
        _rename_references(value, new_name_by_old) for value in original_values
    ]
    _assert_values_pass_write_validation(imported_field, imported_values)


def _duplicate_database(user: AbstractUser, table: Table) -> Table:
    duplicated_database = CoreHandler().duplicate_application(user, table.database)
    return Table.objects.get(database=duplicated_database)


def _duplicate_table(user: AbstractUser, table: Table) -> Table:
    return TableHandler().duplicate_table(user, table)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "duplicate", [_duplicate_database, _duplicate_table], ids=["database", "table"]
)
def test_duplication_keeps_rich_text_image_references_valid(
    data_fixture,
    use_tmp_media_root,
    duplicate: Callable[[AbstractUser, Table], Table],
):
    user = data_fixture.create_user()
    table, field, user_files = _create_rich_text_rows_with_images(data_fixture, user)

    duplicated_table = duplicate(user, table)

    duplicated_field = duplicated_table.field_set.get(name=field.name).specific
    duplicated_values = _rich_text_values(duplicated_table, duplicated_field)
    assert duplicated_values == _rich_text_values(table, field)
    assert set().union(*map(extract_user_file_names, duplicated_values)) == {
        user_file.name for user_file in user_files
    }
    _assert_values_pass_write_validation(duplicated_field, duplicated_values)
