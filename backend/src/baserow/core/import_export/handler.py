import base64
import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from io import IOBase
from os.path import join
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import SuspiciousOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils.encoding import force_bytes

import jsonschema
import zipstream
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from jsonschema import validate
from loguru import logger
from opentelemetry import trace

from baserow.config.settings.base import BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL
from baserow.contrib.database.constants import EXPORT_WORKSPACE_CREATE_ARCHIVE
from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportApplicationIdsNotFound,
    ImportExportResourceDoesNotExist,
    ImportExportResourceInBeingImported,
    ImportExportResourceInvalidFile,
    ImportExportResourceUntrustedSignature,
)
from baserow.core.import_export.utils import chunk_generator
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import (
    Application,
    ExportApplicationsJob,
    ImportApplicationsJob,
    ImportExportResource,
    ImportExportTrustedSource,
    Workspace,
)
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.signals import application_created, application_imported
from baserow.core.storage import (
    ExportZipFile,
    _create_storage_dir_if_missing_and_open,
    get_default_storage,
)
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    InvalidFileStreamError,
)
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import ChildProgressBuilder, grouper, stream_size
from baserow.version import VERSION

tracer = trace.get_tracer(__name__)

WORKSPACE_EXPORTS_LIMIT = 5
EXPORT_FORMAT_VERSION = "1.0.0"
MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "manifest_signature.json"
INDENT = settings.DEBUG and 4 or None


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

    def compute_checksums(
        self, zip_file: ExportZipFile, storage: Storage
    ) -> Dict[str, str]:
        """
        Computes the SHA-256 checksum for each file in the provided zip file.
        * for files that are stored in UserFile model, the checksum is retrieved from
            file name as that file name contains checksum
        * for json data files, the checksum is also stored on file name
        * for all other files, the checksum is computed from the file content

        :param zip_file: The zip stream containing the files to compute checksums for.
        :param storage: The storage instance used to read the file.
        :return: A dictionary where the keys are file names and the values are their
            corresponding SHA-256 checksums.
        """

        checksums = {}
        user_file_handler = UserFileHandler()
        for file_info in zip_file.info_list():
            file_name = file_info["name"]
            try:
                # UserFile name pattern is <unique>_<checksum>.<extension>
                # so we can extract checksum from file name
                checksums[file_name] = user_file_handler.user_file_sha256(file_name)
            except ValueError:
                file_path = user_file_handler.user_file_path(user_file_name=file_name)
                if storage.exists(file_path):
                    checksums[file_name] = self.compute_checksum_from_file(
                        file_path, storage
                    )
                else:
                    # If file does not exist on storage, and it's name doesn't match
                    # UserFile name pattern, we can't calculate checksum
                    checksums[file_name] = ""
        return checksums

    def compute_checksum_from_file(self, full_path: str, storage: Storage) -> str:
        """
        Computes the SHA-256 checksum for a file stored in the given storage.

        This method reads the file in chunks and computes its SHA-256 checksum.

        :param full_path: The full path to the file in the storage.
        :param storage: The storage instance used to read the file.
        :return: The computed SHA-256 checksum as a hexadecimal string.
        """

        computed_checksum = hashlib.sha256()
        with storage.open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                computed_checksum.update(chunk)
        return computed_checksum.hexdigest()

    def mark_resource_invalid(self, resource: ImportExportResource):
        """
        Marks a resource as invalid by setting the `is_valid` field to False.

        :param resource: The resource to be marked as invalid.
        """

        resource.is_valid = False
        resource.save()

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
            for file_name in files:
                storage.delete(join(path, file_name))

            for directory in directories:
                self.clean_storage(join(path, directory), storage)

            storage.delete(path)

    def export_application(
        self,
        app: Application,
        zip_file: ExportZipFile,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Dict:
        """
        Exports a single application (structure, content and assets) to a zip file.
        :param app: Application instance that will be exported
        :param zip_file: The ExportZipFile instance where the exported files will be
            stored.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param storage: The storage where the export will be stored.
        :param progress_builder: A progress builder that allows for publishing progress.
        :return: The exported and serialized application.
        """

        application = app.specific
        application_type = application_type_registry.get_by_model(application)

        app_id = uuid.uuid4().hex
        base_app_path = f"{application_type.type}__{app_id}"

        with application_type.export_safe_transaction_context(application):
            exported_application = application_type.export_serialized(
                application, import_export_config, zip_file, storage, progress_builder
            )

        data_file_content = json.dumps(exported_application, indent=INDENT)
        sha256 = hashlib.sha256(force_bytes(data_file_content)).hexdigest()
        base_schema_path = f"{base_app_path}_{sha256}.json"

        zip_file.add(chunk_generator(data_file_content), base_schema_path)
        application_data = {
            "id": application.id,
            "type": application_type.type,
            "name": application.name,
            "uuid": app_id,
            "total_files": 1,
            "files": {"schema": base_schema_path},
        }
        return application_data

    def export_multiple_applications(
        self,
        applications: List[Application],
        zip_file: ExportZipFile,
        import_export_config: ImportExportConfig,
        storage: Storage,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        """
        Exports multiple applications (structure, content, and assets) to a zip file.

        :param applications: List of Application instances to be exported.
        :param zip_file: The ExportZipFile instance where the exported files will be
            stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param storage: The storage instance where the export will be stored.
        :param progress_builder: A progress builder that allows for publishing progress.
        :return: A list of dictionaries representing the exported applications.
        """

        exported_applications = []
        progress = ChildProgressBuilder.build(progress_builder, len(applications))

        for app in applications:
            child_builder = progress.create_child_builder(represents_progress=1)
            exported_application = self.export_application(
                app, zip_file, import_export_config, storage, child_builder
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
        zip_file: ExportZipFile,
        import_export_config: ImportExportConfig,
        storage: Storage,
    ) -> Dict[str, Any]:
        """
        Creates a manifest file for the exported applications.

        This method generates a manifest file that includes metadata about the exported
        applications, such as their schema, contents, and configuration. The manifest
        file is saved to the specified storage.

        :param exported_applications: A list of dictionaries representing the exported
            applications.
        :param zip_file: The ExportZipFile instance where the manifest will be added.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param storage: The storage instance used to read the file.
        :return manifest_data: A dictionary containing the manifest data.
        """

        checksums = self.compute_checksums(zip_file, storage)
        manifest_data = {
            "version": EXPORT_FORMAT_VERSION,
            "baserow_version": VERSION,
            "total_files": len(checksums) + 2,
            "configuration": {"only_structure": import_export_config.only_structure},
            "applications": {},
            "checksums": checksums,
        }

        for application in exported_applications:
            manifest_data["applications"].setdefault(
                application["type"],
                {"version": EXPORT_FORMAT_VERSION, "configuration": {}, "items": []},
            )["items"].append(application)

        zip_file.add(json.dumps(manifest_data, indent=INDENT), MANIFEST_NAME)
        return manifest_data

    def _get_keys(
        self, trusted_source: ImportExportTrustedSource
    ) -> Tuple[rsa.RSAPrivateKey, bytes]:
        """
        Return the private key and public key pem from the trusted source.

        :param trusted_source: The trusted source to get the keys from.
        :return: A tuple containing the private key and public key (pem).
        """

        private_key = serialization.load_pem_private_key(
            trusted_source.private_key.encode("utf-8"),
            password=None,
            backend=default_backend(),
        )
        public_key = serialization.load_pem_public_key(
            trusted_source.public_key.encode("utf-8"), backend=default_backend()
        )
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_key, public_key_pem

    def _create_keys(self) -> Tuple[rsa.RSAPrivateKey, bytes, bytes]:
        """
        Generates a new RSA key pair and returns the private and public keys.

        :return: A tuple containing the private key, public key (pem), and private key
            (pem).
        """

        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        public_key = private_key.public_key()

        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_key, public_key_pem, private_key_pem

    def get_or_create_key_pair(self) -> Tuple[rsa.RSAPrivateKey, bytes]:
        """
        Retrieves or generates a key pair for the given user.

        This method first attempts to retrieve an existing key pair from the
        `ImportExportTrustedSource` model. If no key pair is found, a new RSA
        key pair is generated, and the private and public keys are serialized
        and stored in the `ImportExportTrustedSource` model.

        :return: A tuple containing the private key and public key (pem).
        """

        try:
            trusted_source = (
                ImportExportTrustedSource.objects.filter(private_key__isnull=False)
                .exclude(private_key="")
                .get()
            )
            private_key, public_key_pem = self._get_keys(trusted_source)
        except ImportExportTrustedSource.DoesNotExist:
            private_key, public_key_pem, private_key_pem = self._create_keys()
            ImportExportTrustedSource.objects.create(
                private_key=private_key_pem.decode("utf-8"),
                public_key=public_key_pem.decode("utf-8"),
            )
        except ImportExportTrustedSource.MultipleObjectsReturned:
            logger.error("Multiple trusted sources found, using the first one.")
            trusted_source = (
                ImportExportTrustedSource.objects.filter(private_key__isnull=False)
                .order_by("id")
                .first()
            )
            private_key, public_key_pem = self._get_keys(trusted_source)

        return private_key, public_key_pem

    def create_manifest_signature(
        self,
        manifest_data: Dict,
        zip_file: ExportZipFile,
    ):
        """
        Signs the manifest file for the exported applications.

        This method generates a digital signature for the manifest file using the user's
        private key. The signature, along with the public key and a timestamp, is saved
        to a signature file in the specified storage.

        :param manifest_data: The manifest data to be signed.
        :param zip_file: The ExportZipFile instance where manifest signature
            will be added.
        """

        manifest_bytes = json.dumps(manifest_data, sort_keys=True).encode()
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(manifest_bytes)
        manifest_hash = digest.finalize()

        private_key, public_key_pem = self.get_or_create_key_pair()
        signature = private_key.sign(
            manifest_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )

        encoded_signature = base64.b64encode(signature).decode("utf-8")

        signature_data = {
            "signature": encoded_signature,
            "public_key_pem": base64.b64encode(public_key_pem).decode("utf-8"),
            "timestamp": datetime.now().isoformat(),
        }

        zip_file.add(
            json.dumps(signature_data, indent=INDENT),
            SIGNATURE_NAME,
        )

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

        export_file_path = self.get_export_storage_path(file_name)

        zip_file = ExportZipFile(
            compress_level=BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
            compress_type=zipstream.ZIP_DEFLATED,
        )

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        exported_applications = self.export_multiple_applications(
            applications,
            zip_file,
            import_export_config,
            storage,
            progress.create_child_builder(represents_progress=90),
        )

        manifest_data = self.create_manifest(
            exported_applications, zip_file, import_export_config, storage
        )

        self.create_manifest_signature(manifest_data, zip_file)

        progress.set_progress(90, state=EXPORT_WORKSPACE_CREATE_ARCHIVE)
        with _create_storage_dir_if_missing_and_open(
            export_file_path, storage
        ) as files_buffer:
            for chunk in zip_file:
                files_buffer.write(chunk)

        with storage.open(export_file_path, "rb") as zip_file_handle:
            with ZipFile(zip_file_handle, "r") as zip_file:
                self.validate_manifest(zip_file)

        resource.size = storage.size(export_file_path)
        resource.is_valid = True
        resource.save()

        progress.set_progress(100)
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

        zip_file_names = zip_file.namelist()

        if MANIFEST_NAME not in zip_file_names:
            raise ImportExportResourceInvalidFile("Manifest file is missing.")

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

            total_files = manifest_data.get("total_files", 0)
            if total_files != len(zip_file_names):
                raise ImportExportResourceInvalidFile(
                    "Manifest file is corrupted: Files count doesn't match"
                )

        core_settings = CoreHandler().get_settings()

        if core_settings.verify_import_signature:
            self.validate_signature(zip_file, manifest_data)

        return manifest_data

    def validate_signature(self, zip_file: ZipFile, manifest_data: Dict):
        """
        Validates the digital signature of the manifest file within the provided zip
        file.

        This method reads the signature file from the zip archive, verifies the digital
        signature using the public key, and checks if the public key is trusted. If the
        signature is invalid or the public key is not trusted, an
        ImportWorkspaceFileCorruptedException is raised.

        :param zip_file: The zip file containing the manifest and signature to be
            validated.
        :param manifest_data: The manifest data to be validated.
        :raises ImportWorkspaceFileCorruptedException: If the signature is invalid or
            the public key is not trusted.
        :raises ImportExportResourceUntrustedSignature: If the manifest is signed
            correctly but the public key is not trusted.
        """

        if SIGNATURE_NAME not in zip_file.namelist():
            raise ImportExportResourceInvalidFile("Signature file is missing.")

        with zip_file.open(SIGNATURE_NAME) as manifest_handler:
            try:
                signature_data = json.load(manifest_handler)
            except json.JSONDecodeError:
                raise ImportExportResourceInvalidFile("Signature file is corrupted.")

            public_key_pem = base64.b64decode(
                signature_data.get("public_key_pem") or ""
            )

            try:
                public_key = serialization.load_pem_public_key(
                    public_key_pem, backend=default_backend()
                )
                decoded_key = public_key_pem.decode("utf-8")
            except ValueError:
                is_trusted = False
            else:
                is_trusted = ImportExportTrustedSource.objects.filter(
                    public_key=decoded_key
                ).exists()

            if not is_trusted:
                raise ImportExportResourceUntrustedSignature(
                    "Signature public key is not trusted."
                )

            manifest_bytes = json.dumps(manifest_data, sort_keys=True).encode()
            digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
            digest.update(manifest_bytes)
            manifest_hash = digest.finalize()

            signature_bytes = base64.b64decode(signature_data.get("signature") or "")

            try:
                public_key.verify(
                    signature_bytes,
                    manifest_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            except InvalidSignature:
                raise ImportExportResourceInvalidFile("Signature verification failed.")

    def validate_checksums(self, manifest: Dict, import_tmp_dir: str, storage: Storage):
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

        checksums = manifest["checksums"]
        for file_path, checksum in checksums.items():
            full_path = join(import_tmp_dir, file_path)

            if not storage.exists(full_path):
                raise ImportExportResourceDoesNotExist(
                    f"The file {file_path} does not exist."
                )

            computed_checksum = self.compute_checksum_from_file(full_path, storage)
            is_valid = computed_checksum == checksum
            validation_results[file_path] = is_valid

        if not all(validation_results.values()):
            raise ImportExportResourceInvalidFile("Checksum validation failed")

    def import_application(
        self,
        workspace: Workspace,
        id_mapping: Dict[str, Any],
        application_manifest: Dict,
        import_tmp_path: str,
        import_export_config: ImportExportConfig,
        zip_file: ZipFile,
        storage: Storage,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Imports a single application into a workspace from the provided data.

        :param workspace: The workspace into which the application will be imported.
        :param id_mapping: A dictionary for mapping old IDs to new IDs during import.
        :param application_manifest: Information from manifest about application.
        :param import_tmp_path: The temporary path where the import files are stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param zip_file: The ZipFile instance containing the application to be imported.
        :param storage: The storage instance to use for file operations.
        :param progress: A progress instance that allows tracking of the import
            progress.
        :return: The imported Application instance.
        """

        data_file_path = join(import_tmp_path, application_manifest["files"]["schema"])
        if not storage.exists(data_file_path):
            raise ImportExportResourceDoesNotExist(
                f"The file {data_file_path} does not exist."
            )

        with storage.open(data_file_path) as data_file:
            application_data = json.load(data_file)

        application_type = application_type_registry.get(application_manifest["type"])
        imported_application = application_type.import_serialized(
            workspace,
            application_data,
            import_export_config,
            id_mapping,
            zip_file,
            storage,
            progress_builder=progress_builder,
        )
        return imported_application

    def import_multiple_applications(
        self,
        user: AbstractUser,
        workspace: Workspace,
        manifest: Dict,
        import_tmp_path: str,
        import_export_config: ImportExportConfig,
        zip_file: ZipFile,
        storage: Storage,
        application_ids: Optional[List[int]] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Imports multiple applications into a workspace from the provided application
        data.

        :param user: The user performing the import operation.
        :param workspace: The workspace into which the applications will be imported.
        :param manifest: A dictionary representing the manifest data of the
            applications.
        :param import_tmp_path: The temporary path where the import files are stored.
        :param import_export_config: Configuration options for the import/export
            process.
        :param zip_file: The ZipFile instance containing the applications to be
            imported.
        :param storage: The storage instance to use for file operations.
        :param application_ids: Optional list of application IDs to import from the
            resource. If not provided, all applications in the resource will be
            imported.
        :param progress: A progress instance that allows tracking of the import
            progress.
        :return: A list of imported Application instances.
        """

        imported_applications = []
        id_mapping: Dict[str, Any] = {}
        next_application_order_value = Application.get_last_order(workspace)

        # Sort the serialized applications so that we import:
        # Database first
        # Applications second
        # Everything else after that.
        def application_priority_sort(application_to_sort):
            return application_type_registry.get(
                application_to_sort
            ).import_application_priority

        prioritized_applications = sorted(
            manifest["applications"].keys(), key=application_priority_sort, reverse=True
        )

        if application_ids:
            available_application_ids = set()
            for app_type in prioritized_applications:
                for item in manifest["applications"][app_type]["items"]:
                    available_application_ids.add(item.get("id"))

            missing_application_ids = set(application_ids) - available_application_ids
            if missing_application_ids:
                raise ImportExportApplicationIdsNotFound(
                    f"The following application IDs were not found in the export: {sorted(missing_application_ids)}"
                )

            filtered_manifest = {"applications": {}}
            for app_type in prioritized_applications:
                filtered_items = []
                for item in manifest["applications"][app_type]["items"]:
                    if item.get("id") in application_ids:
                        filtered_items.append(item)
                if filtered_items:
                    filtered_manifest["applications"][app_type] = {
                        "items": filtered_items
                    }
            manifest = filtered_manifest
            prioritized_applications = list(filtered_manifest["applications"].keys())

        application_count = sum(
            len(manifest["applications"][application_type]["items"])
            for application_type in prioritized_applications
        )
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=application_count
        )

        for application_type in prioritized_applications:
            for application_manifest in manifest["applications"][application_type][
                "items"
            ]:
                try:
                    with transaction.atomic():
                        imported_application = self.import_application(
                            workspace,
                            id_mapping,
                            application_manifest,
                            import_tmp_path,
                            import_export_config,
                            zip_file,
                            storage,
                            progress.create_child_builder(represents_progress=1),
                        )
                except Exception as exc:  # noqa
                    # Trash the already imported applications so the user won't see
                    # a partial import, but he will be able to restore them if he
                    # wants to until they are permanently deleted by the trash task.
                    for application in imported_applications:
                        TrashHandler.trash(user, workspace, application, application)
                    raise exc
                else:
                    imported_application.order = next_application_order_value
                    next_application_order_value += 1
                    imported_applications.append(imported_application)

        Application.objects.bulk_update(imported_applications, ["order"])
        return imported_applications

    def extract_files_from_zip(
        self,
        tmp_import_path: str,
        zip_file: ZipFile,
        storage: Storage,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Extracts files from a zip archive to a specified temporary import path.

        This method iterates over the files in the provided zip archive and saves each
        file to the specified temporary import path using the provided storage instance.

        :param tmp_import_path: The temporary directory where the files will be
            extracted.
        :param zip_file: The ZipFile instance containing the files to be extracted.
        :param storage: The storage instance used to save the extracted files.
        :param progress_builder: A progress builder that allows for publishing progress.
        """

        file_list = zip_file.infolist()
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(file_list)
        )

        for file_info in file_list:
            extracted_file_path = join(tmp_import_path, file_info.filename)
            with zip_file.open(file_info) as extracted_file:
                file_content = extracted_file.read()
                storage.save(extracted_file_path, ContentFile(file_content))
            progress.increment()

    def import_workspace_applications(
        self,
        user: AbstractUser,
        workspace: Workspace,
        resource: ImportExportResource,
        application_ids: Optional[List[int]] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Imports applications into a workspace from a zip file.

        :param user: The user performing the import operation.
        :param workspace: The workspace into which the applications will be imported.
            for storing temporary files.
        :param resource: The resource containing the zip file to be imported.
        :param application_ids: Optional list of application IDs to import from the
            resource. If not provided, all applications in the resource will be
            imported.
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

        progress.set_progress(2)

        if not storage.exists(import_file_path):
            raise ImportExportResourceDoesNotExist(
                f"The file {import_file_path} does not exist."
            )

        if not resource.is_valid:
            raise ImportExportResourceInvalidFile(
                f"The file {import_file_path} is invalid or corrupted."
            )

        progress.set_progress(5)

        with storage.open(import_file_path, "rb") as zip_file_handle:
            with ZipFile(zip_file_handle, "r") as zip_file:
                try:
                    manifest_data = self.validate_manifest(zip_file)
                except Exception as e:  # noqa
                    self.mark_resource_invalid(resource)
                    raise

                self.extract_files_from_zip(
                    import_tmp_path,
                    zip_file,
                    storage,
                    progress.create_child_builder(represents_progress=10),
                )

                try:
                    self.validate_checksums(manifest_data, import_tmp_path, storage)
                except Exception as e:  # noqa
                    self.mark_resource_invalid(resource)
                    raise

                only_structure = manifest_data["configuration"].get(
                    "only_structure", False
                )

                import_export_config = ImportExportConfig(
                    include_permission_data=False,
                    reduce_disk_space_usage=False,
                    only_structure=only_structure,
                )

                imported_applications = self.import_multiple_applications(
                    user,
                    workspace,
                    manifest_data,
                    import_tmp_path,
                    import_export_config,
                    zip_file,
                    storage,
                    application_ids,
                    progress.create_child_builder(represents_progress=80),
                )

                for application in imported_applications:
                    application_type = application_type_registry.get_by_model(
                        application
                    )
                    for signal in [application_created, application_imported]:
                        signal.send(
                            self,
                            application=application,
                            user=user,
                            type_name=application_type.type,
                        )

        progress.set_progress(95)
        self.clean_storage(import_tmp_path, storage)
        self.clean_storage(import_file_path, storage)
        progress.set_progress(100)

        return imported_applications

    def mark_resource_for_deletion(
        self,
        user: AbstractUser,
        resource_id: str,
        delete_used_resources_after_days: int = settings.BASEROW_IMPORT_EXPORT_RESOURCE_REMOVAL_AFTER_DAYS,
    ):
        """
        Marks a resource for deletion by setting the `marked_for_deletion` field to
        True. The resource will be per

        :param user: The user performing the delete operation.
        :param resource_id: The UUID of the resource to be deleted.
        :param delete_used_resources_after_days: The number of days after which the
            resource will be permanently deleted if not used by any job.
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
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            days=delete_used_resources_after_days
        )
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
            return model.objects.filter(
                resource_id=OuterRef("id"), updated_on__gte=cutoff_time
            ).is_pending_or_running()

        running_exports = resources_in_use_by(ExportApplicationsJob)
        running_imports = resources_in_use_by(ImportApplicationsJob)

        trashed_resources = (
            ImportExportResource.objects_and_trash.filter(
                marked_for_deletion=True,
            )
            .annotate(
                in_use_by_export=Exists(running_exports),
                in_use_by_import=Exists(running_imports),
            )
            .filter(in_use_by_export=False, in_use_by_import=False)
            .order_by("-updated_on")
        )

        storage = get_default_storage()

        for chunk in grouper(20, trashed_resources):
            resources_to_delete = []
            for resource in chunk:
                try:
                    archive_path = self.export_file_path(resource.get_archive_name())

                    if storage.exists(archive_path):
                        storage.delete(archive_path)

                    temp_folder_path = self.export_file_path(str(resource.uuid))
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

            ImportExportResource.objects_and_trash.filter(
                id__in=resources_to_delete
            ).delete()

    def add_trusted_public_key(self, name, public_key_data):
        """
        Adds a new trusted public key to the `ImportExportTrustedSource` model.

        :param name: The name of the trusted public key.
        :param public_key_data: Public key in PEM format.
        """

        try:
            decoded_public_key = base64.b64decode(public_key_data)
            public_key = serialization.load_pem_public_key(
                decoded_public_key, backend=default_backend()
            )
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
        except Exception:  # noqa
            logger.error("Provided public key is invalid or in wrong format")
            return

        try:
            source = ImportExportTrustedSource.objects.get(public_key=public_key_pem)
            logger.warning(
                f"Key with that public key already exists with ID #{source.id}"
            )
        except ImportExportTrustedSource.DoesNotExist:
            ImportExportTrustedSource.objects.create(
                name=name,
                public_key=public_key_pem,
            )
            logger.info("Public key added", name)
        except ImportExportTrustedSource.MultipleObjectsReturned:
            logger.error("Multiple keys found with the same name", name)

    def list_trusted_public_keys(self):
        """
        Lists all trusted public keys.

        This method retrieves and prints all the trusted public keys stored in the
        database.
        """

        col_widths = {
            "ID": 10,
            "Created At": 20,
            "Name": 30,
            "Public Key (last 50 chars)": 50,
        }
        headers = list(col_widths.keys())
        divider = "-" * (sum(col_widths.values()) + len(col_widths) * 3)

        print(divider)
        print(
            f"{headers[0]:<{col_widths['ID']}} | "
            f"{headers[1]:<{col_widths['Created At']}} | "
            f"{headers[2]:<{col_widths['Name']}} | "
            f"{headers[3]:<{col_widths['Public Key (last 50 chars)']}}"
        )
        print(divider)

        for record in ImportExportTrustedSource.objects.all():
            public_key_str = record.public_key.replace(
                "-----END PUBLIC KEY-----", ""
            ).replace("\n", "")[-50:]
            created_at_str = record.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"{str(record.id):<{col_widths['ID']}} | "
                f"{created_at_str:<{col_widths['Created At']}} | "
                f"{record.name:<{col_widths['Name']}} | "
                f"{public_key_str:<{col_widths['Public Key (last 50 chars)']}}"
            )
        print(divider)

    def delete_trusted_public_key(self, source_id: str):
        """
        Deletes a trusted public key by its ID.

        This method attempts to delete a trusted public key from the
        `ImportExportTrustedSource` model based on the provided ID.

        Only keys without an associated private key can be deleted.

        :param source_id: The ID of the trusted public key to be deleted.
        """

        try:
            source = ImportExportTrustedSource.objects.get(id=source_id)
        except ImportExportTrustedSource.DoesNotExist:
            logger.warning(f"Trusted public key for ID #{source_id} does not exist")
        else:
            if source.private_key:
                logger.warning(
                    f"Trusted source cannot be removed as it has a private key"
                )
            else:
                source.delete()
                logger.info(f"Trusted public key for ID #{source_id} removed")
