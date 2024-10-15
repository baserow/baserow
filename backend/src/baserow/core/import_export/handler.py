import json
import uuid
import zipfile
from io import IOBase
from os.path import join
from typing import Any, Dict, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db.models import QuerySet

from opentelemetry import trace

from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportWorkspaceFileCorruptedException,
    ImportWorkspaceResourceDoesNotExist,
)
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import (
    Application,
    ExportApplicationsJob,
    ImportApplicationsJob,
    ImportResource,
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
JSON_FILE_NAME = "data/workspace_export.json"


class ImportExportHandler(metaclass=baserow_trace_methods(tracer)):
    def export_application(
        self,
        app: Application,
        import_export_config: ImportExportConfig,
        files_zip: ZipFile,
        storage: Storage,
        progress: Progress,
    ) -> Dict:
        """
        Exports a single application (structure, content and assets) to a zip file.
        :param app: Application instance that will be exported
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param files_zip: ZipFile instance to which the exported data will be written
        :param storage: The storage where the export will be stored.
        :param progress: Progress instance that allows tracking of the export progress.
        :return: The exported and serialized application.
        """

        application = app.specific
        application_type = application_type_registry.get_by_model(application)

        with application_type.export_safe_transaction_context(application):
            exported_application = application_type.export_serialized(
                application, import_export_config, files_zip, storage
            )
        progress.increment()
        return exported_application

    def export_multiple_applications(
        self,
        applications: List[Application],
        import_export_config: ImportExportConfig,
        files_zip: ZipFile,
        storage: Storage,
        progress: Progress,
    ) -> List[Dict]:
        """
        Exports multiple applications (structure, content and assets) to a zip file.
        :param applications: Application instances that will be exported
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param files_zip: ZipFile instance to which the exported data will be written
        :param storage: The storage where the export will be stored.
        :param progress: Progress instance that allows tracking of the export progress.
        :return: The exported and serialized application.
        """

        exported_applications = []

        for app in applications:
            exported_application = self.export_application(
                app, import_export_config, files_zip, storage, progress
            )
            exported_applications.append(exported_application)
        return exported_applications

    def export_json_data(
        self,
        file_name: str,
        exported_applications: List[Dict],
        files_zip: ZipFile,
        storage: Storage,
    ) -> None:
        """
        Export application data (structure and content) to a json file
        and put it in the zip file.

        :param file_name: name of the file that will be created with exported data
        :param exported_applications: exported and serialized applications
        :param files_zip: ZipFile instance to which the exported data will be written
        :param storage: The storage where the files will be stored
        """

        temp_json_file_name = f"temp_{file_name}_{uuid.uuid4()}.json"
        temp_json_file_path = storage.save(temp_json_file_name, ContentFile(""))

        with storage.open(temp_json_file_path, "w") as temp_json_file:
            json.dump(exported_applications, temp_json_file, indent=None)

        with storage.open(temp_json_file_path, "rb") as temp_json_file:
            files_zip.write(temp_json_file.name, file_name)
        storage.delete(temp_json_file_path)

    def export_file_path(self, file_name: str) -> str:
        """
        Returns the full path for given file_name, which will be used
        to store the file within storage

        :param file_name: name of file
        :return: full path to the file
        """

        return join(settings.EXPORT_FILES_DIRECTORY, file_name)

    def export_workspace_applications(
        self,
        workspace: Workspace,
        import_export_config: ImportExportConfig,
        applications: List[Application],
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> str:
        """
        Create zip file with exported applications. If applications param is provided,
        only those applications will be exported.

        :param workspace: The workspace of which the applications will be exported.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param applications: A list of Application instances that will be exported.
        :param storage: The storage where the files will be stored. If not provided
            the default storage will be used.
        :param progress_builder: A progress builder that allows for publishing progress.
        :return: name of the zip file with exported applications
        """

        storage = storage or get_default_storage()
        applications = applications or []

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        export_app_progress = progress.create_child(80, len(applications))

        zip_file_name = f"workspace_{workspace.id}_{uuid.uuid4()}.zip"

        export_path = self.export_file_path(zip_file_name)

        with _create_storage_dir_if_missing_and_open(
            export_path, storage
        ) as files_buffer:
            with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
                exported_applications = self.export_multiple_applications(
                    applications,
                    import_export_config,
                    files_zip,
                    storage,
                    export_app_progress,
                )
                self.export_json_data(
                    JSON_FILE_NAME, exported_applications, files_zip, storage
                )
                progress.increment(by=20)
        return zip_file_name

    def list(self, workspace_id: int, performed_by: AbstractUser) -> QuerySet:
        """
        Lists all workspace application exports for the given workspace id
        if the provided user is in the same workspace.

        :param workspace_id: The workspace ID of which the applications are exported.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :return: A queryset for workspace export jobs that were created for the given
            workspace.
        """

        handler = CoreHandler()
        workspace = handler.get_workspace(workspace_id)

        handler.check_permissions(
            performed_by,
            ReadWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        return (
            ExportApplicationsJob.objects.filter(
                workspace_id=workspace_id,
                state=JOB_FINISHED,
                user=performed_by,
            )
            .select_related("user")
            .order_by("-updated_on", "-id")[:WORKSPACE_EXPORTS_LIMIT]
        )

    def get_import_job_by_file_name(self, file_name: str) -> ImportApplicationsJob:
        """
        Retrieves an ImportApplicationsJob instance by the given file name.

        :param file_name: The name of the file associated with the import job.
        :return: The ImportApplicationsJob instance if found, otherwise None.
        """

        return ImportApplicationsJob.objects.filter(file_name=file_name).first()

    def get_workspace_or_raise_exception(self, user: AbstractUser, workspace_id: int):
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

    def upload_import_file(
        self,
        user: AbstractUser,
        file_name: str,
        stream: IOBase,
        workspace: Workspace,
        storage: Storage = None,
    ):
        """
        Uploads an import file to the specified workspace.

        This method validates the provided file stream, saves the file to the
        storage, and creates an ImportResource record in the database.

        :param user: The user performing the upload operation.
        :param file_name: The name of the file to be uploaded.
        :param stream: The file stream to be uploaded.
        :param workspace: Workspace instance to which the file will
            be uploaded.
        :param storage: The storage instance to use for file operations.
            If not provided, the default storage will be used.
        :raises InvalidFileStreamError: If the provided stream is not readable.
        :return: The created ImportResource instance.
        """

        if not hasattr(stream, "read"):
            raise InvalidFileStreamError("The provided stream is not readable.")

        self.validate_import_file(stream=stream)

        storage = storage or get_default_storage()

        import_resource = ImportResource.objects.create(
            uploaded_by=user,
            original_name=file_name,
            workspace_id=workspace.id,
        )

        full_path = self.export_file_path(import_resource.name)
        storage.save(full_path, stream)
        stream.close()

        return import_resource

    def validate_import_file(self, stream):
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

    def import_application(
        self,
        application_data: Dict,
        workspace: Workspace,
        import_export_config: ImportExportConfig,
        zip_file: ZipFile,
        storage: Storage,
        id_mapping: Dict[str, Any],
        progress: Progress,
    ) -> Application:
        """
        Imports a single application into a workspace from the provided application
        data.

        :param application_data: A dictionary representing the application to be
            imported.
        :param workspace: The workspace into which the application will be imported.
        :param import_export_config: Configuration options for the import/export
            process.
        :param zip_file: The zip file containing the exported application.
        :param storage: The storage instance to use for file operations.
        :param id_mapping: A dictionary for mapping old IDs to new IDs during import.
        :param progress: A progress instance that allows tracking of the import
            progress.
        :return: The imported Application instance.
        """

        application_type = application_type_registry.get(application_data["type"])
        imported_application = application_type.import_serialized(
            workspace,
            application_data,
            import_export_config,
            id_mapping,
            zip_file,
            storage,
        )
        progress.increment()
        return imported_application

    def import_multiple_applications(
        self,
        workspace: Workspace,
        application_data: List[Dict],
        import_export_config: ImportExportConfig,
        zip_file: ZipFile,
        storage: Storage,
        progress: Progress,
    ) -> List[Application]:
        """
        Imports multiple applications into a workspace from the provided application
        data.

        :param workspace: The workspace into which the applications will be
            imported.
        :param application_data: A list of dictionaries representing the
            applications to be imported.
        :param import_export_config: Configuration options for the
            import/export process.
        :param zip_file: The zip file containing the exported applications.
        :param storage: The storage instance to use for file operations.
        :param progress: A progress instance that allows tracking of the
            import progress.
        :return: A list of imported Application instances.
        """

        imported_applications = []

        id_mapping: Dict[str, Any] = {}
        next_application_order_value = Application.get_last_order(workspace)

        for application in application_data:
            imported_application = self.import_application(
                application,
                workspace,
                import_export_config,
                zip_file,
                storage,
                id_mapping,
                progress,
            )
            imported_application.order = next_application_order_value
            next_application_order_value += 1
            imported_applications.append(imported_application)
        return imported_applications

    def extract_exported_applications(self, zip_file: ZipFile) -> List[Dict]:
        """
        Extracts the exported applications from a given zip file.

        :param zip_file: The zip file containing the exported applications.
        :return: A list of dictionaries representing the exported applications.
        :raises ImportWorkspaceFileCorruptedException: If the JSON file is not
        found in the zip file.
        """

        file_list = zip_file.namelist()

        if JSON_FILE_NAME not in file_list:
            raise ImportWorkspaceFileCorruptedException("Import file is corrupted")

        with zip_file.open(JSON_FILE_NAME) as export_handler:
            exported_applications = json.load(export_handler)
        return exported_applications

    def import_workspace_applications(
        self,
        user: AbstractUser,
        workspace: Workspace,
        file_name: str,
        import_export_config: ImportExportConfig,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Imports applications into a workspace from a zip file.

        :param user: The user performing the import operation.
        :param workspace: The workspace into which the applications will be imported.
        :param file_name: The name of the zip file containing the exported applications.
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

        import_resource = ImportResource.objects.filter(
            workspace_id=workspace.id, name=file_name
        ).first()

        if not import_resource:
            raise ImportWorkspaceResourceDoesNotExist("Import file does not exist.")

        file_path = self.export_file_path(file_name)

        if not storage.exists(file_path):
            raise ImportWorkspaceResourceDoesNotExist(
                f"The file {file_name} does not exist."
            )

        progress.increment(by=5)

        with storage.open(file_path, "rb") as zip_file_handle:
            with ZipFile(zip_file_handle, "r") as zip_file:
                exported_applications = self.extract_exported_applications(zip_file)

                progress.increment(by=15)
                import_app_progress = progress.create_child(
                    70, len(exported_applications)
                )

                imported_applications = self.import_multiple_applications(
                    workspace,
                    exported_applications,
                    import_export_config,
                    zip_file,
                    storage,
                    import_app_progress,
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
                progress.increment(by=10)
        return imported_applications

    def delete_resource(
        self, workspace_id: int, resource_id: str, storage: Storage = None
    ):
        """
        Deletes an import resource and its associated file from storage.

        :param workspace_id: The ID of the workspace to which the resource belongs.
        :param resource_id: The ID of the resource to be deleted.
        :param storage: The storage instance to use for file operations.
            If not provided, the default storage will be used.
        :raises ImportWorkspaceResourceDoesNotExist: If the resource does not exist.
        """

        import_resource = ImportResource.objects.filter(
            workspace_id=workspace_id, id=resource_id
        ).first()
        if not import_resource:
            raise ImportWorkspaceResourceDoesNotExist("Resource does not exist.")

        storage = storage or get_default_storage()
        full_path = self.export_file_path(import_resource.name)
        storage.delete(full_path)
        import_resource.delete()
