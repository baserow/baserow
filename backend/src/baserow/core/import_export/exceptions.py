class ImportExportResourceInvalidFile(Exception):
    message = """The file you are trying to import is corrupted.
    Please try again with a different file."""


class ImportExportResourceDoesNotExist(Exception):
    message = """The requested resource does not exist."""


class ImportExportResourceInBeingImported(Exception):
    message = """The resource is currently being imported."""


class ImportExportResourceUntrustedSignature(Exception):
    message = """The signature of the resource is not trusted."""


class ImportExportApplicationIdsNotFound(Exception):
    message = """One or more of the specified application IDs were not found in the export file."""
