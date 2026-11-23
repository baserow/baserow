from django.db import OperationalError

from baserow.api.errors import (
    ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.snapshots.errors import ERROR_SNAPSHOT_DOES_NOT_EXIST
from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import JOB_CANCELLED
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import JobType
from baserow.core.psycopg import errors
from baserow.core.registries import application_type_registry
from baserow.core.service import CoreService
from baserow.core.snapshots.exceptions import SnapshotDoesNotExist

from .models import CreateSnapshotJob, RestoreSnapshotJob


class CreateSnapshotJobType(JobType):
    type = "create_snapshot"
    model_class = CreateSnapshotJob
    max_count = 1
    # The snapshot is committed with the transaction of the job, which locks the row
    # of the job first, see `_check_not_cancelled`. A snapshot whose job was cancelled
    # no longer counts as being created, so it must never be committed afterwards.
    lock_on_cancel = True

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        SnapshotDoesNotExist: ERROR_SNAPSHOT_DOES_NOT_EXIST,
        DatabaseSnapshotMaxLocksExceededException: ERROR_MAX_LOCKS_PER_TRANSACTION_EXCEEDED,
    }

    job_exceptions_map = {
        DatabaseSnapshotMaxLocksExceededException: DatabaseSnapshotMaxLocksExceededException.message
    }

    serializer_field_names = ["snapshot"]

    @property
    def serializer_field_overrides(self):
        from baserow.api.snapshots.serializers import SnapshotSerializer

        return {
            "snapshot": SnapshotSerializer(),
        }

    def transaction_atomic_context(self, job: CreateSnapshotJob):
        application = CoreService().get_application(
            job.user, job.snapshot.snapshot_from_application.id
        )
        application_type = application_type_registry.get_by_model(application)
        return application_type.export_safe_transaction_context(application)

    def is_cancellable(self, job: CreateSnapshotJob) -> bool:
        # The snapshot is ready once its copy is committed.
        return job.snapshot is None or job.snapshot.snapshot_to_application_id is None

    def run(self, job: CreateSnapshotJob, progress):
        from .actions import CreateSnapshotActionType

        action_type_registry.get(CreateSnapshotActionType.type).do(
            job.user, job.snapshot, progress
        )
        self._check_not_cancelled(job)

    def _check_not_cancelled(self, job: CreateSnapshotJob) -> None:
        """
        Locks the row of the job as the last step of its transaction, so that a
        cancellation is either noticed here or refused until the snapshot is
        committed, see `is_cancellable`.

        :raises JobCancelled: If the job was cancelled in the meantime.
        """

        try:
            state = JobHandler.lock_job(job).state
        except OperationalError as exc:
            # A snapshot is copied in a REPEATABLE READ transaction, where locking
            # the row fails if a cancellation changed it in the meantime.
            if isinstance(exc.__cause__, errors.SerializationFailure):
                raise JobCancelled() from exc
            raise
        if state == JOB_CANCELLED:
            raise JobCancelled()

    def before_delete(self, job):
        # Delete the dangling snapshot if it didn't finish correctly but the snapshot is
        # still there.
        if not job.finished and job.snapshot_id is not None:
            job.snapshot.delete()


class RestoreSnapshotJobType(JobType):
    type = "restore_snapshot"
    model_class = RestoreSnapshotJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        SnapshotDoesNotExist: ERROR_SNAPSHOT_DOES_NOT_EXIST,
    }

    serializer_field_names = ["snapshot"]

    @property
    def serializer_field_overrides(self):
        from baserow.api.snapshots.serializers import SnapshotSerializer

        return {
            "snapshot": SnapshotSerializer(),
        }

    def run(self, job: RestoreSnapshotJob, progress):
        from .actions import RestoreSnapshotActionType

        action_type_registry.get(RestoreSnapshotActionType.type).do(
            job.user, job.snapshot, progress
        )
