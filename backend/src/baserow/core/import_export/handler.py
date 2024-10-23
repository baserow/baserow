import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from io import IOBase
from itertools import islice
from os.path import join
from typing import Any, Dict, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import SuspiciousOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db.models import OuterRef, Q, QuerySet, Subquery

import jsonschema
from jsonschema import validate
from loguru import logger
from opentelemetry import trace

from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportResourceDoesNotExist,
    ImportExportResourceInBeingImported,
    ImportExportResourceInvalidFile,
)
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import (
    Application,
    ExportApplicationsJob,
    ImportApplicationsJob,
    ImportExportResource,
    Workspace,
)
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.signals import application_created
from baserow.core.storage import (
    _create_storage_dir_if_missing_and_open,
    get_default_storage,
)
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    InvalidFileStreamError,
)
from baserow.core.utils import ChildProgressBuilder, Progress, stream_size

tracer = trace.get_tracer(__name__)

WORKSPACE_EXPORTS_LIMIT = 5
EXPORT_FORMAT_VERSION = "1.0.0"
MANIFEST_NAME = "manifest.json"
INDENT = 4


class ImportExportHandler(metaclass=baserow_trace_methods(tracer)):
    def get_workspace_or_raise(self, user: AbstractUser, workspace_id: int):
        """
        Retrieves a workspace by its ID and checks if the user has read permissions.

        This method fetches the workspace using the provided workspace ID and verifies
        that the user has the necessary read permissions for the workspace. If the
        workspace does not exist or the user lacks permissions, appropriate exceptions
        are raised.

        :param user: The user performing the operation.
        :param workspace_id: The ID of the workspace to retrieve.
        :raises WorkspaceDoesNotExist: If the workspace does not exist.
        :raises PermissionDenied: If the user does not have read permissions
            for the workspace.
        :return: The retrieved Workspace instance.
        """

        core_handler = CoreHandler()
        workspace = core_handler.get_workspace(workspace_id)

        core_handler.check_permissions(
            user,
            ReadWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return workspace

    def compute_checksum(self, file_path: str, storage: Storage):
        """
        Computes the SHA-256 checksum of a file.

        :param file_path: The path to the file for which the checksum is computed.
        :param storage: The storage instance used to read the file.
        :return: The computed SHA-256 checksum as a hexadecimal string.
        """

        sha256_hash = hashlib.sha256()

        with storage.open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def clean_storage(self, path: str, storage: Storage):
        """
        Deletes all files associated with the given export ID.

        This method deletes all files associated with the given export ID from the
        specified storage.

        :param path: The directory containing the files to be deleted.
        :param storage: The storage instance used to delete the files.
        """

        try:
            directories, files = storage.listdir(path)
        except NotADirectoryError:
            storage.delete(path)
        else:
            for directory in directories:
                self.clean_storage(join(path, directory), storage)

            for file_name in files:
                storage.delete(join(path, file_name))
            storage.delete(path)

    def export_application(
        self,
        app: Application,
        export_tmp_path: str,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress: Progress,
    ) -> Dict:
        """
        Exports a single application (structure, content and assets) to a zip file.
        :param app: Application instance that will be exported
        :param export_tmp_path: Temporary path where the export files will be stored.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param storage: The storage where the export will be stored.
        :param progress: Progress instance that allows tracking of the export progress.
        :return: The exported and serialized application.
        """

        application = app.specific
        application_type = application_type_registry.get_by_model(application)

        app_id = uuid.uuid4().hex
        base_app_path = f"{application_type.type}/{app_id}"
        base_media_path = f"{base_app_path}_media.zip"
        export_media_path = join(export_tmp_path, base_media_path)

        with _create_storage_dir_if_missing_and_open(
            export_media_path, storage
        ) as files_buffer:
            with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
                with application_type.export_safe_transaction_context(application):
                    exported_application = application_type.export_serialized(
                        application, import_export_config, files_zip, storage
                    )

        base_data_path = f"{base_app_path}_data.json"
        export_data_path = join(export_tmp_path, base_data_path)
        with storage.open(export_data_path, "w") as json_file:
            json.dump(exported_application, json_file, indent=INDENT)

        progress.increment()
        return {
            "id": application.id,
            "type": application_type.type,
            "name": application.name,
            "uuid": uuid.uuid4().hex,
            "files": {
                "data": {
                    "file": base_data_path,
                    "checksum": self.compute_checksum(export_data_path, storage),
                },
                "media": {
                    "file": base_media_path,
                    "checksum": self.compute_checksum(export_media_path, storage),
                },
            },
        }

    def export_multiple_applications(
        self,
        applications: List[Application],
        export_tmp_path: str,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress: Progress,
    ) -> List[Dict]:
        """
        Exports multiple applications (structure, content, and assets) to a zip file.

        :param applications: List of Application instances to be exported.
        :param export_tmp_path: Temporary path where the export files will be stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param storage: The storage instance where the export will be stored.
        :param progress: Progress instance to track the export progress.
        :return: A list of dictionaries representing the exported applications.
        """

        exported_applications = []

        for app in applications:
            exported_application = self.export_application(
                app, export_tmp_path, import_export_config, storage, progress
            )
            exported_applications.append(exported_application)
        return exported_applications

    def get_export_storage_path(self, *args) -> str:
        return str(join(settings.EXPORT_FILES_DIRECTORY, *args))

    def export_file_path(self, file_name: str) -> str:
        """
        Returns the full path for given file_name, which will be used
        to store the file within storage

        This is for consistency with serializers that require this method

        :param file_name: name of file
        :return: full path to the file
        """

        return self.get_export_storage_path(file_name)

    def create_manifest(
        self,
        exported_applications: List[Dict],
        export_tmp_path: str,
        storage: Storage,
    ):
        """
        Creates a manifest file for the exported applications.

        This method generates a manifest file that includes metadata about the exported
        applications, such as their schema, contents, and configuration. The manifest
        file is saved to the specified storage.

        :param exported_applications: A list of dictionaries representing the exported
            applications.
        :param export_tmp_path: Temporary path where the export files will be stored.
        :param storage: The storage instance to use for file operations.
        """

        export_path = join(export_tmp_path, MANIFEST_NAME)
        manifest_data = {
            "version": EXPORT_FORMAT_VERSION,
            "configuration": {"structure_only": False},
            "applications": {},
        }

        for application in exported_applications:
            manifest_data["applications"].setdefault(
                application["type"],
                {"version": EXPORT_FORMAT_VERSION, "configuration": {}, "items": []},
            )["items"].append(application)

        with _create_storage_dir_if_missing_and_open(
            export_path, storage
        ) as file_handler:
            file_handler.write(json.dumps(manifest_data, indent=INDENT).encode("utf-8"))

    def export_workspace_applications(
        self,
        applications: List[Application],
        import_export_config: ImportExportConfig,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> ImportExportResource:
        """
        Create zip file with exported applications. If applications param is provided,
        only those applications will be exported.

        :param applications: A list of Application instances that will be exported.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param storage: The storage where the files will be stored. If not provided
            the default storage will be used.
        :param progress_builder: A progress builder that allows for publishing progress.
        :return: The ImportExportResource instance that represents the exported file.
        """

        resource = ImportExportResource.objects.create()
        file_name = resource.get_archive_name()

        storage = storage or get_default_storage()
        applications = applications or []
        export_id = uuid.uuid4().hex

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        export_app_progress = progress.create_child(80, len(applications))

        export_file_path = self.get_export_storage_path(file_name)
        export_tmp_path = self.get_export_storage_path(export_id)

        exported_applications = self.export_multiple_applications(
            applications,
            export_tmp_path,
            import_export_config,
            storage,
            export_app_progress,
        )

        self.create_manifest(exported_applications, export_tmp_path, storage)
        self.move_files_to_zip(
            exported_applications, export_file_path, export_tmp_path, storage
        )

        progress.increment(by=15)
        self.clean_storage(export_tmp_path, storage)
        progress.increment(by=5)

        resource.size = storage.size(export_file_path)
        resource.is_valid = True
        resource.save()
        return resource

    def list_exports(self, performed_by: AbstractUser, workspace_id: int) -> QuerySet:
        """
        Lists all workspace application exports for the given workspace id
        if the provided user is in the same workspace.

        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :param workspace_id: The workspace ID of which the applications are exported.
        :return: A queryset for workspace export jobs that were created for the given
            workspace.
        """

        self.get_workspace_or_raise(performed_by, workspace_id)

        return (
            ExportApplicationsJob.objects.filter(
                workspace_id=workspace_id,
                state=JOB_FINISHED,
                user=performed_by,
                resource__is_valid=True,
            )
            .select_related("user", "resource")
            .order_by("-updated_on", "-id")[:WORKSPACE_EXPORTS_LIMIT]
        )

    def move_files_to_zip(
        self,
        applications: List[Dict],
        export_path: str,
        export_tmp_path: str,
        storage: Storage,
    ):
        """
        Moves exported application files and the manifest file into a zip archive.

        This method creates a zip file at the specified export path and adds the
        exported application files and the manifest file to it.

        :param applications: A list of dictionaries representing the exported
            applications.
        :param export_path: The path where the final zip file will be created.
        :param export_tmp_path: Temporary path where the export files will be stored.
        :param storage: The storage instance used to read the files.
        """

        with _create_storage_dir_if_missing_and_open(
            export_path, storage
        ) as files_buffer:
            with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
                for application in applications:
                    for record in application["files"].values():
                        file_path = record["file"]
                        full_file_path = join(export_tmp_path, file_path)
                        with storage.open(full_file_path, "rb") as tmp_file:
                            files_zip.write(tmp_file.name, file_path)

                manifest_path = join(export_tmp_path, MANIFEST_NAME)
                with storage.open(manifest_path, "rb") as tmp_file:
                    files_zip.write(tmp_file.name, MANIFEST_NAME)

    def get_import_storage_path(self, *args) -> str:
        return str(join(settings.IMPORT_FILES_DIRECTORY, *args))

    def create_resource_from_file(
        self,
        user: AbstractUser,
        file_name: str,
        stream: IOBase,
        storage: Storage = None,
    ) -> ImportExportResource:
        """
        This method validates the provided file stream, saves the file to the
        storage, and creates an ImportResource record in the database.

        :param user: The user performing the upload operation.
        :param file_name: The name of the file to be uploaded.
        :param stream: The file stream to be uploaded.
        :param storage: The storage instance to use for file operations.
            If not provided, the default storage will be used.
        :raises InvalidFileStreamError: If the provided stream is not readable.
        :return: The created resource instance.
        """

        if not hasattr(stream, "read"):
            raise InvalidFileStreamError("The provided stream is not readable.")

        resource = ImportExportResource.objects.create(
            created_by=user, original_name=file_name, size=stream_size(stream)
        )

        self.validate_uploaded_file(stream=stream)

        storage = storage or get_default_storage()

        full_path = self.get_import_storage_path(resource.get_archive_name())
        storage.save(full_path, stream)

        with storage.open(full_path, "rb") as zip_file_handle:
            with ZipFile(zip_file_handle, "r") as zip_file:
                self.validate_manifest(zip_file)

        resource.is_valid = True
        resource.save()
        stream.close()
        return resource

    def validate_uploaded_file(self, stream: IOBase):
        """
        Validates the import file by checking its size and format.

        :param stream: The file stream to be validated.
        :raises FileSizeTooLargeError: If the file size exceeds the allowed limit.
        :raises InvalidFileStreamError: If the file is not a valid zip file.
        """

        size = stream_size(stream)

        if size > settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB:
            raise FileSizeTooLargeError(
                settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB,
                "The provided file is too large.",
            )

        if not zipfile.is_zipfile(stream):
            raise InvalidFileStreamError("The provided file is not a valid zip file.")

    def validate_manifest(self, zip_file):
        """
        Validates the manifest file within the provided zip file.

        This method reads the manifest file from the zip archive, validates its JSON
        structure against the appropriate schema, and checks for any corruption.
        If the manifest file is corrupted or does not conform to the expected schema,
        an ImportWorkspaceFileCorruptedException is raised.

        :param zip_file: The zip file containing the manifest to be validated.
        :raises ImportWorkspaceFileCorruptedException:
            If the manifest file is corrupted or does not conform to the expected
            schema.
        :return: The validated manifest data as a dictionary.
        """

        schema_dir = os.path.join(settings.BASE_DIR, "../core/import_export/schema")
        with zip_file.open(MANIFEST_NAME) as manifest_handler:
            try:
                manifest_data = json.load(manifest_handler)
            except json.JSONDecodeError:
                raise ImportExportResourceInvalidFile("Manifest file is corrupted.")

            manifest_version = manifest_data.get("version")
            manifest_schema_file = f"schema_v{manifest_version}.json"

            with open(f"{schema_dir}/{manifest_schema_file}") as schema_file:
                schema = json.load(schema_file)

            try:
                validate(instance=manifest_data, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                raise ImportExportResourceInvalidFile(
                    f"Manifest file is corrupted: {e.message}"
                )
        return manifest_data

    def validate_checksum(self, manifest: Dict, import_tmp_dir: str, storage: Storage):
        """
        Validates the checksums of the files extracted from the import zip file.

        This method computes the SHA-256 checksum for each file listed in the manifest
        and compares it with the expected checksum provided in the manifest. If any
        checksum does not match, an ImportWorkspaceFileCorruptedException is raised.

        :param manifest: The manifest data containing the expected checksums.
        :param import_tmp_dir: The temporary directory where the files have been
            extracted.
        :param storage: The storage instance used to read the files.
        :raises ImportWorkspaceFileCorruptedException: If any file's checksum does not
            match the expected checksum.
        """

        validation_results = {}

        applications = manifest["applications"]
        for application_types in applications.values():
            for application_data in application_types["items"]:
                for file_data in application_data["files"].values():
                    file_path = file_data["file"]
                    computed_checksum = self.compute_checksum(
                        join(import_tmp_dir, file_path), storage
                    )
                    is_valid = computed_checksum == file_data["checksum"]
                    validation_results[file_path] = is_valid

        if not all(validation_results.values()):
            raise ImportExportResourceInvalidFile("Checksum validation failed")

    def import_application(
        self,
        workspace: Workspace,
        id_mapping: Dict[str, Any],
        application_data: Dict,
        import_tmp_path: str,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress: Progress,
    ) -> Application:
        """
        Imports a single application into a workspace from the provided data.

        :param workspace: The workspace into which the application will be imported.
        :param id_mapping: A dictionary for mapping old IDs to new IDs during import.
        :param application_data: Serialized data of the application to be imported.
        :param import_tmp_path: The temporary path where the import files are stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param storage: The storage instance to use for file operations.
        :param progress: A progress instance that allows tracking of the import
            progress.
        :return: The imported Application instance.
        """

        data_file_name = application_data["files"]["data"]["file"]
        media_file_name = application_data["files"]["media"]["file"]

        with storage.open(join(import_tmp_path, data_file_name)) as data_file:
            application_data = json.load(data_file)

        with storage.open(join(import_tmp_path, media_file_name)) as media_file_handle:
            with ZipFile(media_file_handle, "r") as media_file:
                application_type = application_type_registry.get(
                    application_data["type"]
                )
                imported_application = application_type.import_serialized(
                    workspace,
                    application_data,
                    import_export_config,
                    id_mapping,
                    media_file,
                    storage,
                )
                progress.increment()
        return imported_application

    def import_multiple_applications(
        self,
        workspace: Workspace,
        manifest: Dict,
        import_tmp_path: str,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress: Progress,
    ) -> List[Application]:
        """
        Imports multiple applications into a workspace from the provided application
        data.

        :param workspace: The workspace into which the applications will be imported.
        :param manifest: A dictionary representing the manifest data of the
            applications.
        :param import_tmp_path: The temporary path where the import files are stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param storage: The storage instance to use for file operations.
        :param progress: A progress instance that allows tracking of the import
            progress.
        :return: A list of imported Application instances.
        """

        imported_applications = []
        id_mapping: Dict[str, Any] = {}
        next_application_order_value = Application.get_last_order(workspace)

        for applications in manifest["applications"].values():
            for application_data in applications["items"]:
                imported_application = self.import_application(
                    workspace,
                    id_mapping,
                    application_data,
                    import_tmp_path,
                    import_export_config,
                    storage,
                    progress,
                )

                imported_application.order = next_application_order_value
                next_application_order_value += 1
                imported_applications.append(imported_application)

        Application.objects.bulk_update(imported_applications, ["order"])
        return imported_applications

    def extract_files_from_zip(
        self, tmp_import_path: str, zip_file: ZipFile, storage: Storage
    ):
        """
        Extracts files from a zip archive to a specified temporary import path.

        This method iterates over the files in the provided zip archive and saves each
        file to the specified temporary import path using the provided storage instance.

        :param tmp_import_path: The temporary directory where the files will be
            extracted.
        :param zip_file: The zip file containing the files to be extracted.
        :param storage: The storage instance used to save the extracted files.
        """

        for file_info in zip_file.infolist():
            extracted_file_path = join(tmp_import_path, file_info.filename)
            with zip_file.open(file_info) as extracted_file:
                file_content = extracted_file.read()
                storage.save(extracted_file_path, ContentFile(file_content))

    def import_workspace_applications(
        self,
        user: AbstractUser,
        workspace: Workspace,
        resource: ImportExportResource,
        import_export_config: ImportExportConfig,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Imports applications into a workspace from a zip file.

        :param user: The user performing the import operation.
        :param workspace: The workspace into which the applications will be imported.
            for storing temporary files.
        :param resource: The resource containing the zip file to be imported.
        :param import_export_config: Configuration options for the import/export
            process.
        :param storage: The storage instance to use for file operations.
            If not provided, the default storage will be used.
        :param progress_builder: A progress builder that allows for publishing progress.
        :raises ImportWorkspaceResourceDoesNotExist: If the import file does not exist.
        :return: A list of imported applications.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)

        storage = storage or get_default_storage()

        if not resource:
            raise ImportExportResourceDoesNotExist("Import file does not exist.")
        elif not resource.is_valid:
            raise ImportExportResourceInvalidFile(
                "Import file is invalid or corrupted."
            )

        archive_name = resource.get_archive_name()

        import_file_path = self.get_import_storage_path(archive_name)
        import_tmp_path = self.get_import_storage_path(resource.uuid.hex)

        # If the path for temporary files exists it means that job process
        # was interrupted, and we need to clean it up before starting the import
        if storage.exists(import_tmp_path):
            self.clean_storage(import_tmp_path, storage)

        if not storage.exists(import_file_path):
            raise ImportExportResourceDoesNotExist(
                f"The file {import_file_path} does not exist."
            )

        if not resource.is_valid:
            raise ImportExportResourceInvalidFile(
                f"The file {import_file_path} is invalid or corrupted."
            )

        progress.increment(by=5)

        with storage.open(import_file_path, "rb") as zip_file_handle:
            with ZipFile(zip_file_handle, "r") as zip_file:
                manifest_data = self.validate_manifest(zip_file)
                self.extract_files_from_zip(import_tmp_path, zip_file, storage)
                self.validate_checksum(manifest_data, import_tmp_path, storage)

                imported_applications = self.import_multiple_applications(
                    workspace,
                    manifest_data,
                    import_tmp_path,
                    import_export_config,
                    storage,
                    progress,
                )

                for application in imported_applications:
                    application_type = application_type_registry.get_by_model(
                        application
                    )
                    application_created.send(
                        self,
                        application=application,
                        user=user,
                        type_name=application_type.type,
                    )

                Application.objects.bulk_update(imported_applications, ["order"])

        self.clean_storage(import_tmp_path, storage)
        self.clean_storage(import_file_path, storage)
        progress.increment(by=95)

        return imported_applications

    def mark_resource_for_deletion(self, user: AbstractUser, resource_id: str):
        """
        Marks a resource for deletion by setting the `marked_for_deletion` field to
        True. The resource will be per

        :param user: The user performing the delete operation.
        :param resource_id: The UUID of the resource to be deleted.
        :raises ImportWorkspaceResourceDoesNotExist: If the resource does not
            exist for the provided user and UUID.
        :raises ImportWorkspaceResourceInBeingImported: If the resource is
            currently being imported.
        """

        resource = ImportExportResource.objects.filter(
            id=resource_id, created_by=user
        ).first()
        if not resource:
            raise ImportExportResourceDoesNotExist("Resource does not exist.")

        # Ensure no import Job is running using this resource
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=3)
        if (
            ImportApplicationsJob.objects.filter(
                resource_id=resource.id, updated_on__gt=cutoff_time
            )
            .is_pending_or_running()
            .exists()
        ):
            raise ImportExportResourceInBeingImported()

        resource.marked_for_deletion = True
        resource.save()

    def permanently_delete_trashed_resources(self):
        """
        Deletes all resources that are marked for deletion. This function ensure no
        resources are deleted if referenced by a running job, unless the job is
        running for more than 3 days with no update (cutoff time).
        """

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=3)

        def resources_in_use_by(model):
            return (
                model.objects.filter(
                    resource_id=OuterRef("id"), updated_on__lte=cutoff_time
                )
                .is_pending_or_running()
                .values("resource_id")[:1]
            )

        running_exports = resources_in_use_by(ExportApplicationsJob)
        running_imports = resources_in_use_by(ImportApplicationsJob)

        trashed_resources = (
            ImportExportResource.objects_and_trash.filter(
                marked_for_deletion=True,
            )
            .exclude(Q(id=Subquery(running_exports)) | Q(id=Subquery(running_imports)))
            .order_by("-updated_on")
        )

        storage = get_default_storage()

        for chunk in islice(trashed_resources, 10):
            resources_to_delete = []
            for resource in chunk:
                try:
                    archive_path = self.export_file_path(resource.get_archive_name())

                    if storage.exists(archive_path):
                        storage.delete(archive_path)

                    temp_folder_path = self.export_file_path(resource.uuid)
                    if storage.exists(temp_folder_path):
                        self.clean_storage(temp_folder_path, storage)
                except (FileNotFoundError, OSError, SuspiciousOperation) as e:
                    logger.error(
                        f"File error deleting files for resource {resource.id}: {e}"
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Unknown error deleting resources' files: {resource.id}: {e}"
                    )
                    continue
                else:
                    resources_to_delete.append(resource.id)

            ImportExportResource.objects.filter(id__in=resources_to_delete).delete()
