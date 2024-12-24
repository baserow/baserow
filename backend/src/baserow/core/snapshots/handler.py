from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import OperationalError
from django.db.models import QuerySet

from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
    is_max_lock_exceeded_exception,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import Job
from baserow.core.models import Application, Snapshot, Workspace
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.signals import application_created
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    SnapshotDoesNotExist,
    SnapshotIsBeingCreated,
    SnapshotIsBeingDeleted,
    SnapshotIsBeingRestored,
    SnapshotNameNotUnique,
)
from baserow.core.storage import get_default_storage
from baserow.core.utils import Progress

from .job_types import CreateSnapshotJobType, RestoreSnapshotJobType
from .operations import (
    CreateSnapshotApplicationOperationType,
    DeleteApplicationSnapshotOperationType,
    ListSnapshotsApplicationOperationType,
    RestoreApplicationSnapshotOperationType,
)
from .tasks import delete_application_snapshot


class SnapshotHandler:
    def _count(self, workspace: Workspace) -> int:
        """
        Helper method to count the number of snapshots in the provided
        workspace.

        :param workspace: The workspace for which to count the snapshots.
        """

        return (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application__workspace=workspace)
            .count()
        )

    def _check_is_in_use(self, snapshot: Snapshot) -> None:
        """
        Checks if the provided snapshot is in use and raises appropriate
        exception if it is.

        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to use
            a snapshot as the data are needed to restore it.
        """

        restoring_jobs_count = (
            JobHandler.get_pending_or_running_jobs(RestoreSnapshotJobType.type)
            .filter(snapshot=snapshot)
            .count()
        )

        if restoring_jobs_count > 0:
            raise SnapshotIsBeingRestored()

        if snapshot.mark_for_deletion is True:
            raise SnapshotIsBeingDeleted()

    def list(self, application_id: int, performed_by: AbstractUser) -> QuerySet:
        """
        Lists all snapshots for the given application id if the provided
        user is in the same workspace as the application.

        :param application_id: The ID of the application for which to list
            snapshots.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :return: A queryset for snapshots that were created for the given
            application.
        """

        try:
            application = (
                Application.objects.filter(id=application_id)
                .select_related("workspace")
                .get()
            )
        except Application.DoesNotExist:
            raise ApplicationDoesNotExist(
                f"The application with id {application_id} does not exist."
            )

        CoreHandler().check_permissions(
            performed_by,
            ListSnapshotsApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        return (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application__id=application_id)
            .select_related("created_by")
            .order_by("-created_at", "-id")
        )

    def start_create_job(
        self, application_id: int, performed_by: AbstractUser, name: str
    ):
        """
        Create a snapshot instance to track the creation of a snapshot and start the job
        to perform the snapshot creation.

        :param application_id: The ID of the application for which to list snapshots.
        :param performed_by: The user performing the operation that should have
            sufficient permissions.
        :param name: The name for the new snapshot.
        :raises ApplicationDoesNotExist: When the application with the provided id does
            not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises MaximumSnapshotsReached: When the workspace has already reached the
            maximum of allowed snapshots.
        :raises ApplicationOperationNotSupported: When the application type doesn't
            support creating snapshots.
        :raises SnapshotIsBeingCreated: When creating a snapshot is already scheduled
            for the application.
        :raises MaxJobCountExceeded: When the user already has a running job to create a
            snapshot of the same type.
        :return: The snapshot object that was created and the started job.
        """

        snapshot = self.create(application_id, performed_by, name)

        job = JobHandler().create_and_start_job(
            performed_by,
            CreateSnapshotJobType.type,
            snapshot=snapshot,
        )

        return {
            "snapshot": snapshot,
            "job": job,
        }

    def create(self, application_id, performed_by, name):
        try:
            application = (
                Application.objects.filter(id=application_id)
                .select_related("workspace")
                .get()
            )
        except Application.DoesNotExist:
            raise ApplicationDoesNotExist(
                f"The application with id {application_id} does not exist."
            )

        CoreHandler().check_permissions(
            performed_by,
            CreateSnapshotApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        app_type = application_type_registry.get_by_model(application.specific_class)
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        max_snapshots = settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP
        if max_snapshots >= 0 and self._count(application.workspace) >= max_snapshots:
            raise MaximumSnapshotsReached()

        creating_jobs_count = (
            JobHandler()
            .get_pending_or_running_jobs(CreateSnapshotJobType.type)
            .filter(snapshot__snapshot_from_application=application)
            .count()
        )
        if creating_jobs_count > 0:
            raise SnapshotIsBeingCreated()

        if (
            Snapshot.objects.restorable()
            .filter(
                snapshot_from_application=application,
                created_by=performed_by,
                name=name,
            )
            .exists()
        ):
            raise SnapshotNameNotUnique()

        snapshot = Snapshot.objects.create(
            snapshot_from_application=application,
            created_by=performed_by,
            name=name,
        )

        return snapshot

    def start_restore_job(
        self,
        snapshot_id: int,
        performed_by: AbstractUser,
    ) -> Job:
        """
        Restores a previously created snapshot with the given ID if the
        provided user is in the same workspace as the application.

        :param snapshot_id: The ID of the snapshot to restore.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises ApplicationOperationNotSupported: When the application type
            doesn't support restoring snapshots.
        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to use
            a snapshot as the data are needed to restore it.
        :raises MaxJobCountExceeded: When the user already has a running
            job to restore a snapshot of the same type.
        :return: The job that can be used to track the restoring.
        """

        try:
            snapshot = (
                Snapshot.objects.filter(id=snapshot_id)
                .select_for_update(of=("self",))
                .select_related("snapshot_from_application__workspace")
                .get()
            )
        except Snapshot.DoesNotExist:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        CoreHandler().check_permissions(
            performed_by,
            RestoreApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        app_type = application_type_registry.get_by_model(
            snapshot.snapshot_from_application.specific_class
        )
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        self._check_is_in_use(snapshot)

        job = JobHandler().create_and_start_job(
            performed_by,
            RestoreSnapshotJobType.type,
            snapshot=snapshot,
        )

        return job

    def _schedule_deletion(self, snapshot: Snapshot):
        snapshot.mark_for_deletion = True
        snapshot.save()
        if snapshot.snapshot_to_application is not None:
            delete_application_snapshot.delay(snapshot.snapshot_to_application.id)

    def delete(self, snapshot_id: int, performed_by: AbstractUser) -> None:
        """
        Deletes a previously created snapshot with the given ID if the
        provided user belongs to the same workspace as the application.

        :param snapshot_id: The ID of the snapshot to delete.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises ApplicationOperationNotSupported: When the application type
            doesn't support deleting snapshots.
        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to delete
            a snapshot as the data are needed to restore it.
        :raises MaxJobCountExceeded: When the user already has a running
            job to delete a snapshot of the same type.
        """

        try:
            snapshot = (
                Snapshot.objects.filter(id=snapshot_id)
                .select_for_update(of=("self",))
                .select_related("snapshot_from_application__workspace")
                .get()
            )
        except Snapshot.DoesNotExist:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        CoreHandler().check_permissions(
            performed_by,
            DeleteApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        app_type = application_type_registry.get_by_model(
            snapshot.snapshot_from_application.specific_class
        )
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        self._check_is_in_use(snapshot)
        self._schedule_deletion(snapshot)

    def delete_by_application(self, application: Application) -> None:
        """
        Deletes all snapshots related to the provided application.

        :param application: Application for which to delete all related
            snapshots.
        """

        application_snapshots = Snapshot.objects.filter(
            snapshot_from_application=application
        ).select_for_update(of=("self",))
        for snapshot in application_snapshots:
            self._schedule_deletion(snapshot)

    def delete_expired(self) -> None:
        """
        Finds all snapshots that are considered expired based on
        BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS and schedules their deletion.
        """

        threshold = datetime.now(tz=timezone.utc) - timedelta(
            days=settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS
        )
        expired_snapshots = Snapshot.objects.filter(
            created_at__lt=threshold
        ).select_for_update(of=("self",))
        for snapshot in expired_snapshots:
            self._schedule_deletion(snapshot)

    def perform_create(self, snapshot: Snapshot, progress: Progress) -> None:
        """
        Creates an actual copy of the original application and stores it as
        another application with its workspace set to None to effectively hide it
        from the system.

        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        """

        storage = get_default_storage()

        if snapshot is None:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        application = snapshot.snapshot_from_application.specific

        CoreHandler().check_permissions(
            snapshot.created_by,
            CreateSnapshotApplicationOperationType.type,
            workspace=workspace,
            context=application,
        )

        application_type = application_type_registry.get_by_model(application)
        snapshot_import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=True,
            workspace_for_user_references=workspace,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )
        try:
            exported_application = application_type.export_serialized(
                application, snapshot_import_export_config, None, storage
            )
        except OperationalError as e:
            # Detect if this `OperationalError` is due to us exceeding the
            # lock count in `max_locks_per_transaction`. If it is, we'll
            # raise a different exception so that we can catch this scenario.
            if is_max_lock_exceeded_exception(e):
                raise DatabaseSnapshotMaxLocksExceededException()
            raise e

        progress.increment(by=50)
        id_mapping = {"import_workspace_id": workspace.id}
        # Set the `snapshot_from` reverse relation so that after
        # `ApplicationType.import_serialized` creates the `Application`,
        # we set the source snapshot so that `get_root()` can be called
        # on this application.
        exported_application["snapshot_from"] = snapshot
        application_type.import_serialized(
            None,
            exported_application,
            snapshot_import_export_config,
            id_mapping,
            None,
            storage,
            progress_builder=progress.create_child_builder(represents_progress=50),
        )

    def perform_restore(self, snapshot: Snapshot, progress: Progress) -> Application:
        """
        Creates an application copy from the snapshotted application. The copy
        will be available as a normal application in the same workspace as the
        original application.

        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :returns: Application that is a copy of the snapshot.
        """

        storage = get_default_storage()

        if snapshot is None:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace
        CoreHandler().check_permissions(
            snapshot.created_by,
            RestoreApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        application = snapshot.snapshot_to_application.specific
        application_type = application_type_registry.get_by_model(application)

        restore_snapshot_import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )
        # Temporary set the workspace for the application so that the permissions can
        # be correctly set during the import process.
        application.workspace = workspace
        exported_application = application_type.export_serialized(
            application, restore_snapshot_import_export_config, None, storage
        )
        progress.increment(by=50)

        imported_application = application_type.import_serialized(
            snapshot.snapshot_from_application.workspace,
            exported_application,
            restore_snapshot_import_export_config,
            {},
            None,
            storage,
            progress_builder=progress.create_child_builder(represents_progress=50),
        )
        imported_application.name = CoreHandler().find_unused_application_name(
            snapshot.snapshot_from_application.workspace, snapshot.name
        )
        imported_application.save()
        application_created.send(self, application=imported_application, user=None)
        return imported_application
