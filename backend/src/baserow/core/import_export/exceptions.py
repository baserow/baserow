class ImportWorkspaceFileCorruptedException(Exception):
    message = """The file you are trying to import is corrupted.
    Please try again with a different file."""


class ImportWorkspaceResourceDoesNotExist(Exception):
    message = """The requested resource does not exist."""
