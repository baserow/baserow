from baserow.core.operations import ApplicationOperationType, WorkspaceCoreOperationType


class ReadWorkspaceAutomaticSnapshotScheduleOperationType(WorkspaceCoreOperationType):
    type = "workspace.read_automatic_snapshot_schedule"


class UpdateWorkspaceAutomaticSnapshotScheduleOperationType(WorkspaceCoreOperationType):
    type = "workspace.update_automatic_snapshot_schedule"


class ReadApplicationAutomaticSnapshotScheduleOperationType(ApplicationOperationType):
    type = "application.read_automatic_snapshot_schedule"


class UpdateApplicationAutomaticSnapshotScheduleOperationType(ApplicationOperationType):
    type = "application.update_automatic_snapshot_schedule"
