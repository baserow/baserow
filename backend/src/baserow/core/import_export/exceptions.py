class ImportExportResourceInvalidFile(Exception):
    message = """The file you are trying to import is corrupted.
    Please try again with a different file."""


class ImportExportResourceDoesNotExist(Exception):
    message = """The requested resource does not exist."""


class ImportExportResourceInBeingImported(Exception):
    message = """The resource is currently being imported."""
