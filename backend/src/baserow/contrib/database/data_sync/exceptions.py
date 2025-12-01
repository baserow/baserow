class PropertyNotFound(Exception):
    """Raised when the property is not found in the data sync."""

    def __init__(self, property, *args, **kwargs):
        self.property = property
        super().__init__(*args, **kwargs)


class UniquePrimaryPropertyNotFound(Exception):
    """
    Raised when the data sync didn't return a property with `unique_primary=True`. At
    least one is required.
    """


class SyncError(Exception):
    """
    This exception can be raised when something goes wrong during the data sync,
    and it doesn't have to fail hard. The provided error will be stored in the
    database, exposed via the API, and readable to the user. It should always be in
    English.
    """


class DataSyncDoesNotExist(Exception):
    """
    Raised when the data sync does not exist.
    """


class SyncDataSyncTableAlreadyRunning(Exception):
    """
    Raised when the table is sync is initiated, but it's already running. Only one sync
    can be running concurrently.
    """


class TwoWayDataSyncNotSupported(Exception):
    """
    Raised when two-way sync is being enabled for a data sync type that doesn't support
    it.
    """
