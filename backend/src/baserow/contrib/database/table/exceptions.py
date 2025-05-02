from baserow.core.exceptions import LockConflict


class TableDoesNotExist(Exception):
    """Raised when trying to get a table that doesn't exist."""


class TableNotInDatabase(Exception):
    """Raised when a provided table does not belong to a database."""

    def __init__(self, table_id=None, *args, **kwargs):
        self.table_id = table_id
        super().__init__(
            f"The table {table_id} does not belong to the database.",
            *args,
            **kwargs,
        )


class InvalidInitialTableData(Exception):
    """Raised when the provided initial table data does not contain a column or row."""


class TableDoesNotBelongToGroup(Exception):
    """Raised when the table does not belong to the related group."""


class InitialSyncTableDataLimitExceeded(Exception):
    """
    Raised when the initial table data limit has been exceeded when creating a new
    table in synchronous way.
    """


class InitialTableDataLimitExceeded(Exception):
    """
    Raised when the initial table data limit has been exceeded when creating a new
    table.
    """


class InitialTableDataDuplicateName(Exception):
    """
    Raised when the initial table data contains duplicate field names.
    """


class FailedToLockTableDueToConflict(LockConflict):
    """
    Raised when the table is in use by some concurrent operation and the lock cannot
    be obtained immediately.
    """


class TableUsageUpdateLocked(Exception):
    """
    Raised when the related `database_tableusageupdate` is locked.
    """
