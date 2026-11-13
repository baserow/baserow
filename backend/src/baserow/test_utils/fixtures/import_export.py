from django.core.files.storage import Storage

from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ImportExportResource, ImportExportTrustedSource
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import (
    _create_storage_dir_if_missing_and_open,
    get_default_storage,
)
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

    def export_workspace_applications_file(self, applications) -> str:
        """
        Exports the applications as a signed workspace export file and returns its
        storage path.
        """

        self.create_import_export_trusted_source()
        handler = ImportExportHandler()
        resource = handler.export_workspace_applications(
            applications=applications,
            import_export_config=ImportExportConfig(
                include_permission_data=False, reduce_disk_space_usage=False
            ),
        )
        return handler.get_export_storage_path(resource.get_archive_name())

    def import_workspace_applications_file(self, export_path, application_ids=None):
        """
        Imports a workspace export file into a new workspace of another user, only
        the given applications when set.
        """

        handler = ImportExportHandler()
        importer = self.create_user()
        target_workspace = self.create_workspace(user=importer)
        with get_default_storage().open(export_path, "rb") as archive:
            import_resource = handler.create_resource_from_file(
                importer, "export.zip", archive
            )
        return handler.import_workspace_applications(
            importer, target_workspace, import_resource, application_ids=application_ids
        )

    def export_and_import_workspace_applications(
        self, applications, application_ids=None
    ):
        export_path = self.export_workspace_applications_file(applications)
        return self.import_workspace_applications_file(export_path, application_ids)

    def disable_import_signature_verification(self):
        core_settings = CoreHandler().get_settings()
        core_settings.verify_import_signature = False
        core_settings.save()
