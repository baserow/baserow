from django.core.files.storage import Storage

from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ImportResource
from baserow.core.storage import _create_storage_dir_if_missing_and_open


class ImportExportWorkspaceFixtures:
    def create_import_resource(self, **kwargs):
        return ImportResource.objects.create(**kwargs)

    def create_import_resource_file(
        self, resource: ImportResource, content: bytes, storage: Storage = None
    ):
        file_path = ImportExportHandler().export_file_path(resource.name)
        with _create_storage_dir_if_missing_and_open(
            file_path, storage=storage
        ) as file_handler:
            file_handler.write(content)
