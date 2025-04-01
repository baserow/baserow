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
from baserow.core.jobs.registries import JobType
from baserow.core.registries import application_type_registry
from baserow.core.service import CoreService
from baserow.core.snapshots.exceptions import SnapshotDoesNotExist

from .models import CreateSnapshotJob, RestoreSnapshotJob


class CreateSnapshotJobType(JobType):
    type = "create_snapshot"
    model_class = CreateSnapshotJob
    max_count = 1

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

    def run(self, job: CreateSnapshotJob, progress):
        from .actions import CreateSnapshotActionType

        action_type_registry.get(CreateSnapshotActionType.type).do(
            job.user, job.snapshot, progress
        )

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
