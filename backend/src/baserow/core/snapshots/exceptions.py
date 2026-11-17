class SnapshotDoesNotExist(Exception):
    """Raise when trying to get a snapshot that does not exist."""


class MaximumSnapshotsReached(Exception):
    """Raise when a new snapshot cannot be created since the max limit is reached."""


class SnapshotIsBeingCreated(Exception):
    """
    Raise when a manipulation with a snapshot is prohibited
    since it is being created.
    """


class SnapshotIsBeingRestored(Exception):
    """
    Raise when a manipulation with a snapshot is prohibited
    since it is being restored.
    """


class SnapshotIsBeingDeleted(Exception):
    """
    Raise when a manipulation with a snapshot is prohibited
    since it is being deleted.
    """


class SnapshotNameNotUnique(Exception):
    """
    Raise when a snapshot name is not unique per application.
    """


class SnapshotKeepIsZero(Exception):
    """
    Raised when creating a snapshot of an application that keeps no snapshots.
    """


class SnapshotKeepFullOfProtected(Exception):
    """
    Raised when creating a snapshot of an application that is at its keep, and
    every snapshot it holds is protected, so none can be replaced.
    """


class SnapshotKeepExceedsAllowance(Exception):
    """
    Raised when raising a keep would reserve more than the workspace's snapshot
    allowance.
    """


class SnapshotKeepAboveMaximum(Exception):
    """
    Raised when a keep is above `BASEROW_MAX_SNAPSHOTS_KEEP_PER_APPLICATION`.
    """


class SnapshotKeepBelowProtected(Exception):
    """
    Raised when lowering a keep below the number of protected snapshots an
    application holds.
    """


class SnapshotKeepChangeDeletesSnapshots(Exception):
    """
    Raised when lowering a keep would delete snapshots, and the deletion wasn't
    confirmed.
    """

    def __init__(self, count: int, *args):
        self.count = count
        super().__init__(
            f"Lowering the keep deletes {count} snapshot(s). Confirm the deletion.",
            *args,
        )
