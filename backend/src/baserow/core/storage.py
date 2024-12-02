from io import BytesIO
from typing import BinaryIO

from django.core.files.storage import Storage, default_storage

# This import is necessary to handle the creation of zip files in a standardized way
# across the application. The ZipStream library is used to manage zip file streams
# efficiently, and we alias it as ExportZipFile for clarity and consistency.
from zipstream import ZipStream as ExportZipFile  # noqa


def get_default_storage() -> Storage:
    """
    Returns the default storage. This method is mainly used to have
    a single point of entry for the default storage, so it's easier to
    test and mock.

    :return: The django default storage.
    """

    return default_storage


class OverwritingStorageHandler:
    def __init__(self, storage=None):
        self.storage = storage or get_default_storage()

    def save(self, name, content):
        if self.storage.exists(name):
            self.storage.delete(name)
        self.storage.save(name, content)


def _create_storage_dir_if_missing_and_open(storage_location, storage=None) -> BinaryIO:
    """
    Attempts to open the provided storage location in binary overwriting write mode.
    If it encounters a FileNotFound error will attempt to create the folder structure
    leading upto to the storage location and then open again.

    :param storage_location: The storage location to open and ensure folders for.
    :param storage: The storage to use, if None will use the default storage.
    :return: The open file descriptor for the storage_location
    """

    storage = storage or get_default_storage()

    try:
        return storage.open(storage_location, "wb+")
    except FileNotFoundError:
        # django's file system storage will not attempt to creating a missing
        # EXPORT_FILES_DIRECTORY and instead will throw a FileNotFoundError.
        # So we first save an empty file which will create any missing directories
        # and then open again.
        storage.save(storage_location, BytesIO())
        return storage.open(storage_location, "wb")
