class TokenDoesNotExist(Exception):
    """Raised when the requested token does not exist."""


class TokenDoesNotBelongToUser(Exception):
    """Raised when a token does not belong to a user."""


class MaximumUniqueTokenTriesError(Exception):
    """
    Raised when the maximum tries has been exceeded while generating a unique token.
    """


class NoPermissionToTable(Exception):
    """
    Raised when a token does not have permissions to perform an operation for a table.
    """


class NoPermissionToLinkedTable(NoPermissionToTable):
    """
    Raised when a token links or joins rows of a table it can't read.
    """

    def __init__(self, table_id, *args, **kwargs):
        self.table_id = table_id
        super().__init__(
            f"The provided token does not have read permissions to the linked table "
            f"{table_id}.",
            *args,
            **kwargs,
        )


class TokenCannotIncludeRowMetadata(Exception):
    """
    Raised if requested to include a row's metadata via token.
    """
