import abc

from baserow.core.operations import ApplicationOperationType, WorkspaceCoreOperationType
from baserow.core.registries import OperationType


class SnapshotOperationType(OperationType, abc.ABC):
    context_scope_name = "snapshot"


class ListSnapshotsApplicationOperationType(ApplicationOperationType):
    type = "application.list_snapshots"
    object_scope_name = "snapshot"


class CreateSnapshotApplicationOperationType(ApplicationOperationType):
    type = "application.create_snapshot"


class RestoreApplicationSnapshotOperationType(SnapshotOperationType):
    type = "application.snapshot.restore"


class DeleteApplicationSnapshotOperationType(SnapshotOperationType):
    type = "application.snapshot.delete"


class UpdateApplicationMaxSnapshotsOperationType(ApplicationOperationType):
    type = "application.update_max_snapshots"


class ReadWorkspaceSnapshotSettingsOperationType(WorkspaceCoreOperationType):
    type = "workspace.read_snapshot_settings"


class UpdateWorkspaceSnapshotSettingsOperationType(WorkspaceCoreOperationType):
    type = "workspace.update_snapshot_settings"
