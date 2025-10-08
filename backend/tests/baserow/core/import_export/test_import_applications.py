import os
import zipfile
from unittest.mock import call, patch

from django.conf import settings

import pytest

from baserow.core.import_export.exceptions import (
    ImportExportApplicationIdsNotFound,
    ImportExportResourceInvalidFile,
)
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.storage import get_default_storage
from baserow.test_utils.zip_helpers import (
    add_file_to_zip,
    change_file_content_in_zip,
    remove_file_from_zip,
)

SOURCES_PATH = os.path.join(
    settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
)
INTERESTING_DB_EXPORT_PATH = f"{SOURCES_PATH}/interesting_database_export.zip"
BUILDER_EXPORT_PATH = f"{SOURCES_PATH}/builder_export.zip"
DEPENDED_APPS_EXPORT_PATH = f"{SOURCES_PATH}/depended_apps_export.zip"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_missing_files(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    data_fixture.create_import_export_trusted_source()

    zip_name = "interesting_database_export_missing_files.zip"
    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    with zipfile.ZipFile(INTERESTING_DB_EXPORT_PATH, "r") as zip_file:
        file_to_remove = zip_file.namelist()[0]

    new_zip_path = remove_file_from_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        file_to_remove,
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with pytest.raises(ImportExportResourceInvalidFile) as err:
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    assert str(err.value) == f"Manifest file is corrupted: Files count doesn't match"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_modified_files(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    data_fixture.create_import_export_trusted_source()

    zip_name = "interesting_database_export_modified_files.zip"
    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    with zipfile.ZipFile(INTERESTING_DB_EXPORT_PATH, "r") as zip_file:
        file_to_change = zip_file.namelist()[0]

    new_zip_path = change_file_content_in_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        file_to_change,
        b"some new content",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with pytest.raises(ImportExportResourceInvalidFile) as err:
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    assert str(err.value) == "Checksum validation failed"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_unexpected_files(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    data_fixture.create_import_export_trusted_source()

    zip_name = "interesting_database_export_unexpected_files.zip"
    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    new_zip_path = add_file_to_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        "unexpected_file.txt",
        b"This file is not listed in manifest.",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with pytest.raises(ImportExportResourceInvalidFile) as err:
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    assert str(err.value) == f"Manifest file is corrupted: Files count doesn't match"


@pytest.mark.import_export_workspace
@pytest.mark.django_db()
@patch("baserow.core.import_export.handler.application_created")
@patch("baserow.core.import_export.handler.application_imported")
def test_import_workspace_applications_calls_signals(
    mock_application_imported,
    mock_application_created,
    data_fixture,
):
    """
    Ensure that after a workspace is imported, the created and imported
    signals are called.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_import_export_trusted_source()
    zip_name = "builder_export.zip"

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    with open(f"{SOURCES_PATH}/{zip_name}", "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    handler = ImportExportHandler()
    with patch(
        "baserow.core.import_export.handler.ImportExportHandler.validate_signature"
    ):
        results = handler.import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    expected_calls = [
        call(
            handler,
            application=results[0],
            user=user,
            type_name="database",
        ),
        call(
            handler,
            application=results[1],
            user=user,
            type_name="builder",
        ),
    ]

    mock_application_created.send.assert_has_calls(expected_calls)
    mock_application_imported.send.assert_has_calls(expected_calls)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_build_workspace_schema_from_zip(data_fixture, use_tmp_media_root):
    user = data_fixture.create_user()
    data_fixture.create_workspace(user=user)

    data_fixture.create_import_export_trusted_source()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="depended_apps_export.zip", is_valid=True
    )

    with open(DEPENDED_APPS_EXPORT_PATH, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    import_file_path = ImportExportHandler().get_import_storage_path(
        resource.get_archive_name()
    )

    storage = get_default_storage()

    with storage.open(import_file_path, "rb") as zip_file_handle:
        with zipfile.ZipFile(zip_file_handle, "r") as zip_file:
            handler = ImportExportHandler()
            workspace_schema = handler._build_workspace_schema_from_zip(zip_file)

    assert workspace_schema == {
        "fields": {18714},
        "tables": {1873},
        "applications": {747, 748},
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_get_applications_to_import_without_dependencies(data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_workspace(user=user)

    workspace_schema = {
        "tables": {1, 2, 3},
        "fields": {10, 20, 30},
        "applications": {1, 2},
    }

    handler = ImportExportHandler()

    application_ids = [1, 2]
    result = handler.get_applications_to_import(application_ids, workspace_schema)
    assert result == [1, 2]

    application_ids = [5, 6]
    with pytest.raises(ImportExportApplicationIdsNotFound):
        result = handler.get_applications_to_import(application_ids, workspace_schema)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_applications_with_dependency_resolution(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_import_export_trusted_source()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="depended_apps_export.zip", is_valid=True
    )

    with open(DEPENDED_APPS_EXPORT_PATH, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    handler = ImportExportHandler()
    builder_app_id = 748

    with patch(
        "baserow.core.import_export.handler.ImportExportHandler.validate_signature"
    ):
        results = handler.import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
            application_ids=[builder_app_id],
        )

    assert len(results) >= 1

    imported_names = [app.name for app in results]
    assert "Application" in imported_names


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_applications_without_dependency_resolution(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_import_export_trusted_source()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="depended_apps_export.zip", is_valid=True
    )

    with open(DEPENDED_APPS_EXPORT_PATH, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    handler = ImportExportHandler()

    with patch(
        "baserow.core.import_export.handler.ImportExportHandler.validate_signature"
    ):
        results = handler.import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    assert len(results) == 2

    imported_names = [app.name for app in results]
    assert "Database" in imported_names
    assert "Application" in imported_names


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_applications_with_nonexistent_ids(data_fixture, use_tmp_media_root):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_import_export_trusted_source()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="depended_apps_export.zip", is_valid=True
    )

    with open(DEPENDED_APPS_EXPORT_PATH, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    handler = ImportExportHandler()

    with patch(
        "baserow.core.import_export.handler.ImportExportHandler.validate_signature"
    ):
        with pytest.raises(ImportExportApplicationIdsNotFound) as exc_info:
            handler.import_workspace_applications(
                user=user,
                workspace=workspace,
                resource=resource,
                application_ids=[999, 1000],
            )

    assert "were not found in the export" in str(exc_info.value)
