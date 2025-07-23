import math

from django.core.exceptions import ValidationError


class InvalidFileStreamError(Exception):
    """Raised when the provided file stream is invalid."""


class FileSizeTooLargeError(Exception):
    """Raised when the provided file is too large."""

    def __init__(self, max_size_bytes, *args, **kwargs):
        self.max_size_mb = math.floor(max_size_bytes / 1024 / 1024)
        super().__init__(*args, **kwargs)


class FileURLCouldNotBeReached(Exception):
    """
    Raised when the provided URL could not be reached or points to an internal
    service.
    """


class InvalidFileURLError(Exception):
    """Raised when the provided file URL is invalid."""


class InvalidUserFileNameError(Exception):
    """Raised when the provided user file name is invalid."""

    def __init__(self, name, *args, **kwargs):
        self.name = name
        super().__init__(*args, **kwargs)


class UserFileDoesNotExist(ValidationError):
    """Raised when a user file with the provided name or id does not exist."""

    def __init__(self, file_names_or_ids, *args, **kwargs):
        if not isinstance(file_names_or_ids, list):
            file_names_or_ids = [file_names_or_ids]
        self.file_names_or_ids = file_names_or_ids
        msg = f"The user files {self.file_names_or_ids} do not exist."
        super().__init__(msg, *args, code="missing", **kwargs)


class MaximumUniqueTriesError(Exception):
    """
    Raised when the maximum tries has been exceeded while generating a unique user file
    string.
    """
