import os
import zipfile
from unittest.mock import call, patch

from django.conf import settings
from django.core.exceptions import SuspiciousOperation

import pytest

from baserow.core.import_export.exceptions import ImportExportResourceInvalidFile
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
def test_validate_safe_path_allows_normal_paths():
    handler = ImportExportHandler()
    result = handler._validate_safe_path("/base/dir", "subdir/file.json")
    assert result == "/base/dir/subdir/file.json"

    result = handler._validate_safe_path("/base/dir", "file.json")
    assert result == "/base/dir/file.json"


@pytest.mark.import_export_workspace
def test_validate_safe_path_rejects_traversal():
    handler = ImportExportHandler()

    with pytest.raises(SuspiciousOperation, match="path traversal"):
        handler._validate_safe_path("/base/dir", "../../../etc/passwd")

    with pytest.raises(SuspiciousOperation, match="path traversal"):
        handler._validate_safe_path("/base/dir", "subdir/../../etc/passwd")

    with pytest.raises(SuspiciousOperation, match="path traversal"):
        handler._validate_safe_path("/base/dir", "/etc/passwd")


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_rejects_zipslip_traversal(data_fixture, use_tmp_media_root, tmp_path):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_import_export_trusted_source()

    zip_name = "zipslip_test.zip"
    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    new_zip_path = add_file_to_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        "../../evil.txt",
        b"malicious content",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    with pytest.raises(ImportExportResourceInvalidFile):
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_extract_files_rejects_files_not_in_manifest(tmp_path, use_tmp_media_root):
    zip_path = f"{tmp_path}/allowlist_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("trusted.txt", "trusted content")
        zf.writestr("extra.txt", "untrusted content")

    storage = get_default_storage()
    extract_dir = "import_test/extract"

    with zipfile.ZipFile(zip_path, "r") as zf:
        with pytest.raises(ImportExportResourceInvalidFile, match="unexpected file"):
            ImportExportHandler().extract_files_from_zip(
                extract_dir, zf, storage, allowed_files=["trusted.txt"]
            )


@pytest.mark.import_export_workspace
def test_build_allowed_files_includes_checksums_and_meta():
    manifest = {"checksums": {"data.json": "abc", "file.bin": "def"}}
    result = ImportExportHandler._build_allowed_files(manifest)
    assert "data.json" in result
    assert "file.bin" in result
    assert "manifest.json" in result
    assert "manifest_signature.json" in result
    assert len(result) == 4


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_validate_checksums_rejects_traversal(tmp_path):
    handler = ImportExportHandler()
    manifest = {"checksums": {"../../etc/passwd": "abc123"}}

    with pytest.raises(SuspiciousOperation, match="path traversal"):
        handler.validate_checksums(manifest, str(tmp_path), get_default_storage())


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_cleans_up_on_checksum_failure(
    data_fixture, use_tmp_media_root, tmp_path
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_import_export_trusted_source()

    zip_name = "cleanup_test.zip"
    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name=zip_name, is_valid=True
    )

    with zipfile.ZipFile(INTERESTING_DB_EXPORT_PATH, "r") as zip_file:
        file_to_change = zip_file.namelist()[0]

    new_zip_path = change_file_content_in_zip(
        INTERESTING_DB_EXPORT_PATH,
        f"{tmp_path}/{zip_name}",
        file_to_change,
        b"tampered content",
    )

    with open(new_zip_path, "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    storage = get_default_storage()
    import_tmp_path = ImportExportHandler().get_import_storage_path(resource.uuid.hex)

    with pytest.raises(ImportExportResourceInvalidFile):
        ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
        )

    assert not storage.exists(import_tmp_path)
