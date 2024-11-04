import os
import zipfile

from django.conf import settings

import pytest

from baserow.core.import_export.exceptions import (
    ImportExportResourceDoesNotExist,
    ImportExportResourceInvalidFile,
)
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.zip_helpers import (
    change_file_content_in_zip,
    remove_file_from_zip,
)

SOURCES_PATH = os.path.join(
    settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
)
INTERESTING_DB_EXPORT_PATH = f"{SOURCES_PATH}/interesting_database_export.zip"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_missing_files(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    data_fixture.create_import_export_trusted_source(user=user)

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

    config = ImportExportConfig(include_permission_data=False)

    with pytest.raises(ImportExportResourceDoesNotExist) as err:
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
            import_export_config=config,
        )

    assert str(err.value) == f"The file {file_to_remove} does not exist."


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_modified_files(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    data_fixture.create_import_export_trusted_source(user=user)

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

    config = ImportExportConfig(include_permission_data=False)

    with pytest.raises(ImportExportResourceInvalidFile) as err:
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
            import_export_config=config,
        )

    assert str(err.value) == "Checksum validation failed"
