from django.core.files.storage import Storage

from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ImportExportResource, ImportExportTrustedSource
from baserow.core.storage import _create_storage_dir_if_missing_and_open
from baserow.test_utils.constants import (
    TEST_IMPORT_EXPORT_PRIVATE_KEY,
    TEST_IMPORT_EXPORT_PUBLIC_KEY,
)


class ImportExportWorkspaceFixtures:
    def create_import_export_resource(self, **kwargs):
        return ImportExportResource.objects.create(**kwargs)

    def create_import_export_resource_file(
        self, resource: ImportExportResource, content: bytes, storage: Storage = None
    ):
        file_path = ImportExportHandler().get_import_storage_path(
            resource.get_archive_name()
        )
        with _create_storage_dir_if_missing_and_open(
            file_path, storage=storage
        ) as file_handler:
            file_handler.write(content)

    def create_import_export_trusted_source(self):
        return ImportExportTrustedSource.objects.create(
            name="Test trusted source",
            private_key=TEST_IMPORT_EXPORT_PRIVATE_KEY,
            public_key=TEST_IMPORT_EXPORT_PUBLIC_KEY,
        )

    def disable_import_signature_verification(self):
        core_settings = CoreHandler().get_settings()
        core_settings.verify_import_signature = False
        core_settings.save()
