class RowDoesNotExist(Exception):
    """Raised when trying to get rows that don't exist."""

    def __init__(self, ids, *args, **kwargs):
        if not isinstance(ids, list):
            ids = [ids]
        self.ids = ids
        super().__init__(*args, **kwargs)


class RowIdsNotUnique(Exception):
    """Raised when trying to update the same rows multiple times"""

    def __init__(self, ids, *args, **kwargs):
        self.ids = ids
        super().__init__(*args, **kwargs)


class ReportMaxErrorCountExceeded(Exception):
    """
    Raised when a the report raises too many error.
    """

    def __init__(self, report, *args, **kwargs):
        self.report = report
        super().__init__("Too many errors", *args, **kwargs)


class CannotCreateRowsInTable(Exception):
    """
    Raised when it's not possible to create rows in the table.
    """


class CannotDeleteRowsInTable(Exception):
    """
    Raised when it's not possible to delete rows in the table.
    """


class InvalidRowLength(Exception):
    """
    Row's length doesn't match expected length based on schema.
    """

    def __init__(self, row_idx: int):
        self.row_idx = row_idx
