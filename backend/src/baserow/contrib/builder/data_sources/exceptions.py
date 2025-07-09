class DataSourceDoesNotExist(Exception):
    """Raised when trying to get a data_source that doesn't exist."""


class DataSourceNotInSamePage(Exception):
    """
    Raised when trying to move a data_source before a data_source on a different
    page.
    """


class DataSourceRefinementForbidden(Exception):
    """
    Raised when a web page visitor tries to apply adhoc filtering, sorting and/or
    search against a schema property that the page designer has not allowed.
    """


class DataSourceNameNotUniqueError(Exception):
    """Raised when trying to set a data source name that already exists"""
