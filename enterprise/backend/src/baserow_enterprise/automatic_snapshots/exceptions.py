class AutomaticSnapshotScheduleDoesNotExist(Exception):
    """Raised when an automatic snapshot schedule doesn't exist."""


class AutomaticSnapshotScheduleAlreadyExists(Exception):
    """
    Raised when creating a schedule for an application, or a workspace default, that
    already has one.
    """


class AutomaticSnapshotScheduleIntervalTooShort(Exception):
    """
    Raised when a schedule runs more often than
    `BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_MIN_INTERVAL_MINUTES` allows.
    """


class AutomaticSnapshotScheduleInvalid(Exception):
    """Raised when the schedule fields are out of range or inconsistent."""
