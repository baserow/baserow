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


class TokenCannotIncludeRowMetadata(Exception):
    """
    Raised if requested to include a row's metadata via token.
    """
