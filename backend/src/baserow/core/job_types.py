from contextlib import contextmanager, nullcontext
from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db import OperationalError, transaction

from loguru import logger
from rest_framework import serializers

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.applications.serializers import (
    InstallTemplateJobApplicationsSerializer,
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED,
    ERROR_PERMISSION_DENIED,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.import_export.errors import (
    ERROR_APPLICATION_IDS_NOT_FOUND,
    ERROR_RESOURCE_DOES_NOT_EXIST,
    ERROR_RESOURCE_IS_INVALID,
)
from baserow.api.import_export.serializers import (
    ExportWorkspaceExportedFileURLSerializerMixin,
    ImportResourceSerializer,
    InstalledApplicationsSerializer,
)
from baserow.api.templates.errors import (
    ERROR_TEMPLATE_BLOCKED,
    ERROR_TEMPLATE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_HAS_NO_CONTENT,
)
from baserow.api.templates.serializers import TemplateSerializer
from baserow.api.workspaces.serializers import WorkspaceSerializer
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    DuplicateApplicationActionType,
    ExportApplicationsActionType,
    ImportApplicationsActionType,
    InstallTemplateActionType,
)
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    DuplicateApplicationMaxLocksExceededException,
    InstallTemplateMaxLocksExceededException,
    PermissionDenied,
    PermissionException,
    TemplateDoesNotExist,
    TemplateFileDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    is_max_lock_exceeded_exception,
)
from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportApplicationIdsNotFound,
    ImportExportResourceDoesNotExist,
    ImportExportResourceInvalidFile,
)
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.jobs.constants import JOB_CANCELLED
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import JobType
from baserow.core.models import (
    Application,
    DuplicateApplicationJob,
    ExportApplicationsJob,
    ImportApplicationsJob,
    ImportExportResource,
    InstallTemplateJob,
    Template,
)
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    ExportWorkspaceOperationType,
    ListApplicationsWorkspaceOperationType,
)
from baserow.core.service import CoreService
from baserow.core.user_templates.exceptions import (
    TemplateBlocked,
    TemplateHasNoContent,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import ChildProgressBuilder, Progress


class DuplicateApplicationJobType(JobType):
    type = "duplicate_application"
    model_class = DuplicateApplicationJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        DuplicateApplicationMaxLocksExceededException: ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED,
    }

    job_exceptions_map = {
        DuplicateApplicationMaxLocksExceededException: DuplicateApplicationMaxLocksExceededException.message
    }

    request_serializer_field_names = ["application_id"]

    request_serializer_field_overrides = {
        "application_id": serializers.IntegerField(
            help_text="The application ID to duplicate.",
        ),
    }

    serializer_field_names = ["original_application", "duplicated_application"]
    serializer_field_overrides = {
        "original_application": PolymorphicApplicationResponseSerializer(
            read_only=True
        ),
        "duplicated_application": PolymorphicApplicationResponseSerializer(
            read_only=True
        ),
    }

    def transaction_atomic_context(self, job: "DuplicateApplicationJob"):
        application = (
            CoreService()
            .get_application(job.user, job.original_application_id)
            .specific
        )
        application_type = application.get_type()
        return application_type.export_safe_transaction_context(application)

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        application = CoreService().get_application(user, values["application_id"])

        return {
            "original_application": application,
        }

    def run(self, job: DuplicateApplicationJob, progress: Progress) -> Application:
        new_application_clone = action_type_registry.get_by_type(
            DuplicateApplicationActionType
        ).do(
            job.user,
            job.original_application,
            progress_builder=progress.create_child_builder(
                represents_progress=progress.total
            ),
        )

        # update the job with the new duplicated application
        job.duplicated_application = new_application_clone
        job.save(update_fields=("duplicated_application",))

        return new_application_clone


class _InstallAlreadyCommitted(Exception):
    """
    Raised at the commit point of a user template install when another run of
    the same job committed first, so that this run is rolled back.
    """

    def __init__(self, installed_application_ids: List[int]):
        super().__init__("The install was already committed by another run.")
        self.installed_application_ids = installed_application_ids


class InstallTemplateJobType(JobType):
    type = "install_template"
    model_class = InstallTemplateJob
    max_count = 1
    # A user template is installed in a transaction the job commits itself, see
    # `_commit_install`.
    lock_on_cancel = True

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
        TemplateFileDoesNotExist: ERROR_TEMPLATE_FILE_DOES_NOT_EXIST,
        TemplateBlocked: ERROR_TEMPLATE_BLOCKED,
        TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
        InstallTemplateMaxLocksExceededException: ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED,
    }

    # The access is checked again when a user template is installed, see `run`.
    # The first matching exception wins, so a subclass comes before its parent.
    job_exceptions_map = {
        UserNotInWorkspace: "The user doesn't belong to the workspace.",
        PermissionException: ERROR_PERMISSION_DENIED[2],
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST[2],
        TemplateBlocked: ERROR_TEMPLATE_BLOCKED[2],
        TemplateHasNoContent: "The content of the template was removed.",
        InstallTemplateMaxLocksExceededException: InstallTemplateMaxLocksExceededException.message,
    }

    request_serializer_field_names = [
        "workspace_id",
        "database_id",
        "airtable_share_url",
    ]

    request_serializer_field_overrides = {
        "workspace_id": serializers.IntegerField(
            required=False,
            help_text="The ID of the workspace where the template will be installed.",
        ),
        "template_id": serializers.IntegerField(
            help_text="The template ID that will be installed.",
        ),
    }

    serializer_field_names = [
        "workspace",
        "template",
        "installed_applications",
    ]
    serializer_field_overrides = {
        "workspace": WorkspaceSerializer(read_only=True),
        "template": TemplateSerializer(read_only=True),
        "installed_applications": InstallTemplateJobApplicationsSerializer(
            read_only=True
        ),
    }

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        handler = CoreHandler()
        workspace = handler.get_workspace(values["workspace_id"])
        CoreHandler().check_permissions(
            user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        # Only the root is looked up, so the id of a revision is unknown too.
        root = Template.objects.filter(
            id=values["template_id"],
            root__isnull=True,
            marked_for_deletion_at__isnull=True,
        ).first()
        if root is not None and root.type == Template.Type.USER:
            # The resolved revision is pinned, so that an update of the template
            # before the job runs doesn't change what's installed.
            template = UserTemplateHandler().get_installable_revision(
                user, root, latest=values.get("latest", False)
            )
        else:
            # ensure everything is ok for the installation, otherwise
            # raise an exception immediately without submitting the job
            template = handler.get_template(values["template_id"])
            handler.get_valid_template_path_or_raise(template)

        return {
            "workspace": workspace,
            "template": template,
        }

    def enhance_queryset(self, queryset):
        return queryset.select_related("workspace", "template__root")

    def transaction_atomic_context(self, job: InstallTemplateJob):
        # The export of a user template runs its own transactions, so `run` opens
        # the transaction of the install itself.
        if job.template.type == Template.Type.USER:
            return nullcontext()
        return super().transaction_atomic_context(job)

    def is_cancellable(self, job: InstallTemplateJob) -> bool:
        # A user template install is committed with its `installed_applications`.
        # An official install sets them in the transaction of the job, so it stays
        # cancellable until it ends.
        return not job.installed_applications

    def run(self, job: InstallTemplateJob, progress: Progress) -> List[Application]:
        progress_builder = progress.create_child_builder(
            represents_progress=progress.total
        )

        if job.template.type == Template.Type.USER:
            return self._run_user_template_install(job, progress_builder)

        installed_applications = action_type_registry.get_by_type(
            InstallTemplateActionType
        ).do(job.user, job.workspace, job.template, progress_builder=progress_builder)

        job.installed_applications = [app.id for app in installed_applications]
        job.save(update_fields=("installed_applications",))

        return installed_applications

    def _run_user_template_install(
        self, job: InstallTemplateJob, progress_builder: ChildProgressBuilder
    ) -> List[Application]:
        """
        Installs the pinned revision of a user template. The export runs first,
        outside any transaction, and everything written into the target workspace,
        the count included, is committed together at the commit point, so that a
        failure or a cancellation leaves nothing behind.
        """

        # A redelivered job that was already installed isn't installed again.
        if job.installed_applications:
            return self._get_installed_applications(job.installed_applications)

        # The access may have changed since the job was requested.
        CoreHandler().check_permissions(
            job.user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=job.workspace,
            context=job.workspace,
        )
        user_template_handler = UserTemplateHandler()
        user_template_handler.check_install_access(job.user, job.template)

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        committed = False
        try:
            with user_template_handler.export_template_content(
                job.template,
                progress_builder=progress.create_child_builder(represents_progress=50),
            ) as resource:
                with transaction.atomic():
                    installed_applications = action_type_registry.get_by_type(
                        InstallTemplateActionType
                    ).do(
                        job.user,
                        job.workspace,
                        job.template,
                        progress_builder=progress.create_child_builder(
                            represents_progress=50
                        ),
                        resource=resource,
                    )
                    self._commit_install(job, installed_applications)
                committed = True
        except _InstallAlreadyCommitted as exc:
            job.installed_applications = exc.installed_application_ids
            return self._get_installed_applications(exc.installed_application_ids)
        except BaseException as exc:
            if committed:
                if not isinstance(exc, Exception):
                    raise
                # The install is committed, so a failure after it, like in the
                # clean-up of the export, doesn't undo it.
                logger.exception(
                    f"The install template job {job.id} failed after its commit."
                )
                return installed_applications
            # Another run of the job may have committed the install in the
            # meantime, and this failure mustn't be saved over its result.
            if isinstance(exc, Exception):
                with transaction.atomic():
                    committed_ids = JobHandler.lock_job(job).installed_applications
                if committed_ids:
                    logger.exception(
                        f"The install template job {job.id} failed, but another "
                        "run of it committed the install."
                    )
                    job.installed_applications = committed_ids
                    return self._get_installed_applications(committed_ids)
            # Nothing was committed, so the job must not be saved as if it had.
            job.installed_applications = []
            # Caught outside the transaction, which is rolled back by now.
            if isinstance(exc, OperationalError) and is_max_lock_exceeded_exception(
                exc
            ):
                raise InstallTemplateMaxLocksExceededException() from exc
            raise

        return installed_applications

    def _commit_install(
        self, job: InstallTemplateJob, installed_applications: List[Application]
    ) -> None:
        """
        Commits the install of a user template, as the last step of its
        transaction. The row of the job stays locked until the transaction
        commits, so a cancellation is either noticed here or refused afterwards,
        see `is_cancellable`.

        :raises JobCancelled: If the job was cancelled in the meantime.
        :raises _InstallAlreadyCommitted: If another run of the job committed
            first.
        """

        locked_job = JobHandler.lock_job(job)
        if locked_job.state == JOB_CANCELLED:
            raise JobCancelled()
        if locked_job.installed_applications:
            raise _InstallAlreadyCommitted(locked_job.installed_applications)

        job.installed_applications = [app.id for app in installed_applications]
        job.save(update_fields=("installed_applications",))

    def _get_installed_applications(
        self, application_ids: List[int]
    ) -> List[Application]:
        return list(
            Application.objects.filter(id__in=application_ids).order_by("order", "id")
        )


@contextmanager
def _empty_transaction_context():
    """
    Each application is isolated, so a single transaction for all of them together is
    unnecessary and increases the risk of incurring into the `max_locks_per_transaction`
    error. The `import_export_handler` creates a transaction for each
    application in a `repeatable_read` isolation level to guarantee consistency in the
    data read.
    """

    yield


class ExportApplicationsJobType(JobType):
    type = "export_applications"
    model_class = ExportApplicationsJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
    }

    job_exceptions_map = {PermissionDenied: ERROR_PERMISSION_DENIED[2]}

    request_serializer_field_names = [
        "application_ids",
        "only_structure",
    ]
    request_serializer_field_overrides = {
        "application_ids": serializers.ListField(
            allow_null=True,
            allow_empty=True,
            required=False,
            child=serializers.IntegerField(),
            help_text=(
                "The application IDs to export. If not provided, all the applications for "
                "the workspace will be exported."
            ),
        ),
        "only_structure": serializers.BooleanField(
            required=False,
            default=False,
            help_text=(
                "If True, only the structure of the applications will be exported. "
                "If False, the data will be included as well."
            ),
        ),
    }

    serializer_mixins = [ExportWorkspaceExportedFileURLSerializerMixin]
    serializer_field_names = ["exported_file_name", "url", "created_on", "workspace_id"]

    def transaction_atomic_context(self, job: "DuplicateApplicationJob"):
        """
        The `import_export_handler` creates a transaction for each application in a
        `repeatable_read` isolation level to guarantee consistency in the data read and
        avoid the `max_locks_per_transaction` error.
        """

        return _empty_transaction_context()

    def fetch_applications(self, user, workspace, application_ids):
        """
        Fetches the applications that are going to be exported. If the user does not
        have access to the workspace or the applications, a PermissionDenied
        exception is raised.

        :param user: The user that is going to export the applications.
        :param workspace: The workspace where the applications are located.
        :param application_ids: The IDs of the applications that are going to be
            exported.
        :return: The applications that are going to be exported.
        :raises PermissionDenied: If the user does not have access to the workspace or
            the applications.
        """

        CoreHandler().check_permissions(
            user,
            ExportWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        applications = Application.objects.filter(
            workspace=workspace, workspace__trashed=False
        )
        if application_ids:
            applications = applications.filter(id__in=application_ids)

        applications = CoreHandler().filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            applications,
            workspace=workspace,
        )

        if application_ids and len(application_ids) != len(applications):
            raise PermissionDenied(
                "Some of the selected applications do not exist or the user does "
                "not have access to them."
            )

        return applications

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        workspace_id = values.get("workspace_id")
        workspace = CoreHandler().get_workspace(workspace_id=workspace_id)

        application_ids = values.get("application_ids") or []
        self.fetch_applications(user, workspace, application_ids)
        only_structure = values.get("only_structure", False)

        return {
            "workspace": workspace,
            "application_ids": application_ids,
            "only_structure": only_structure,
        }

    def run(self, job: ExportApplicationsJob, progress: Progress):
        applications = self.fetch_applications(
            job.user, job.workspace, job.application_ids
        )

        progress_builder = progress.create_child_builder(
            represents_progress=progress.total
        )

        resource = action_type_registry.get_by_type(ExportApplicationsActionType).do(
            job.user,
            workspace=job.workspace,
            applications=applications,
            only_structure=job.only_structure,
            progress_builder=progress_builder,
        )

        job.resource = resource


class ImportApplicationsJobType(JobType):
    type = "import_applications"
    model_class = ImportApplicationsJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        ImportExportResourceDoesNotExist: ERROR_RESOURCE_DOES_NOT_EXIST,
        ImportExportResourceInvalidFile: ERROR_RESOURCE_IS_INVALID,
        ImportExportApplicationIdsNotFound: ERROR_APPLICATION_IDS_NOT_FOUND,
    }

    job_exceptions_map = {
        ImportExportResourceDoesNotExist: ImportExportResourceDoesNotExist.message,
        ImportExportResourceInvalidFile: ImportExportResourceInvalidFile.message,
        ImportExportApplicationIdsNotFound: ImportExportApplicationIdsNotFound.message,
    }

    request_serializer_field_names = ["resource_id", "application_ids"]
    request_serializer_field_overrides = {
        "resource_id": serializers.IntegerField(
            min_value=1,
            help_text="The ID of the import resource that contains the applications.",
        ),
        "application_ids": serializers.ListField(
            allow_null=True,
            allow_empty=True,
            required=False,
            child=serializers.IntegerField(),
            help_text=(
                "The application IDs to import from the resource. If not provided, all the applications in "
                "the resource will be imported."
            ),
        ),
    }

    serializer_field_names = ["installed_applications", "workspace_id", "resource"]
    serializer_field_overrides = {
        "workspace_id": serializers.IntegerField(),
        "installed_applications": InstalledApplicationsSerializer(
            source="application_ids"
        ),
        "resource": ImportResourceSerializer(),
    }

    def transaction_atomic_context(self, job: "DuplicateApplicationJob"):
        """
        The `import_export_handler` imports every application in a separated transaction
        to avoid the `max_locks_per_transaction` error.
        """

        return _empty_transaction_context()

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        workspace_id = values.get("workspace_id")
        workspace = ImportExportHandler().get_workspace_or_raise(user, workspace_id)

        resource = ImportExportResource.objects.filter(
            id=values.get("resource_id"), created_by=user
        ).first()

        if not resource:
            raise ImportExportResourceDoesNotExist("Import file does not exist.")
        elif not resource.is_valid:
            raise ImportExportResourceInvalidFile(
                "Import file is invalid or corrupted."
            )

        application_ids = values.get("application_ids") or []

        return {
            "workspace": workspace,
            "resource": resource,
            "application_ids": application_ids,
        }

    def run(self, job: ImportApplicationsJob, progress: Progress):
        workspace = ImportExportHandler().get_workspace_or_raise(
            job.user, job.workspace_id
        )

        progress_builder = progress.create_child_builder(
            represents_progress=progress.total
        )

        imported_applications = action_type_registry.get_by_type(
            ImportApplicationsActionType
        ).do(
            job.user,
            workspace=workspace,
            resource=job.resource,
            application_ids=job.application_ids,
            progress_builder=progress_builder,
        )

        job.application_ids = [app.id for app in imported_applications]
