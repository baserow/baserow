import json
import os
import zipfile

from django.conf import settings

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportResourceInvalidFile,
    ImportExportResourceUntrustedSignature,
)
from baserow.core.import_export.handler import ImportExportHandler
from baserow.test_utils.zip_helpers import (
    change_file_content_in_zip,
    get_file_content_from_zip,
)

SOURCES_PATH = os.path.join(
    settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
)
INTERESTING_DB_EXPORT_PATH = f"{SOURCES_PATH}/interesting_database_export.zip"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_signature_and_check_enabled(
    data_fixture, use_tmp_media_root, tmp_path
):
    user = data_fixture.create_user()

    data_fixture.create_import_export_trusted_source()
    zip_name = "interesting_database_without_signature_disabled_check.zip"

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    new_zip_path = change_file_content_in_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        "manifest_signature.json",
        "",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with open(new_zip_path, "rb") as zip_file_handle:
        with zipfile.ZipFile(zip_file_handle, "r") as zip_file:
            with pytest.raises(ImportExportResourceInvalidFile) as err:
                ImportExportHandler().validate_manifest(
                    zip_file=zip_file,
                )
    assert str(err.value) == "Signature file is corrupted."


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_signature_and_check_disabled(
    data_fixture, use_tmp_media_root, tmp_path
):
    user = data_fixture.create_user()

    core_settings = CoreHandler().get_settings()
    core_settings.verify_import_signature = False
    core_settings.save()

    data_fixture.create_import_export_trusted_source()
    zip_name = "interesting_database_without_signature_enabled_check.zip"

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    new_zip_path = change_file_content_in_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        "manifest_signature.json",
        "",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with open(new_zip_path, "rb") as zip_file_handle:
        with zipfile.ZipFile(zip_file_handle, "r") as zip_file:
            result = ImportExportHandler().validate_manifest(
                zip_file=zip_file,
            )
    assert result is not None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_signature_data(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()

    data_fixture.create_import_export_trusted_source()

    zip_name = "interesting_database_without_signature_data.zip"

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    content = get_file_content_from_zip(
        INTERESTING_DB_EXPORT_PATH, "manifest_signature.json"
    )

    signature_data = json.loads(content)
    signature_data.pop("signature")

    new_zip_path = change_file_content_in_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        "manifest_signature.json",
        json.dumps(signature_data),
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with open(new_zip_path, "rb") as zip_file_handle:
        with zipfile.ZipFile(zip_file_handle, "r") as zip_file:
            with pytest.raises(ImportExportResourceInvalidFile) as err:
                ImportExportHandler().validate_manifest(
                    zip_file=zip_file,
                )
    assert str(err.value) == "Signature verification failed."


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_no_trusted_source(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()

    data_fixture.create_import_export_resource(
        created_by=user, original_name="interesting_database.zip", is_valid=True
    )

    with open(INTERESTING_DB_EXPORT_PATH, "rb") as zip_file_handle:
        with zipfile.ZipFile(zip_file_handle, "r") as zip_file:
            with pytest.raises(ImportExportResourceUntrustedSignature) as err:
                ImportExportHandler().validate_manifest(
                    zip_file=zip_file,
                )
    assert str(err.value) == "Signature public key is not trusted."
