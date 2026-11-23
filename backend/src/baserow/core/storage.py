import os
import posixpath
from io import BytesIO
from typing import BinaryIO, Collection, Iterator

from django.core.files.storage import FileSystemStorage, Storage, default_storage

from loguru import logger

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


def storage_lists_by_prefix(storage: Storage) -> bool:
    """
    Whether `iter_storage_names_with_prefixes` lists the storage once per prefix
    instead of reading a folder once for all the prefixes.

    :param storage: The storage to list.
    :return: True for the supported cloud storages.
    """

    from storages.backends.azure_storage import AzureStorage
    from storages.backends.gcloud import GoogleCloudStorage
    from storages.backends.s3 import S3Storage

    return isinstance(storage, (S3Storage, GoogleCloudStorage, AzureStorage))


def iter_storage_names_with_prefixes(
    storage: Storage, folder: str, name_prefixes: Collection[str]
) -> Iterator[str]:
    """
    Yields the names of the stored files directly in the folder whose file name
    starts with one of the prefixes. Local disk reads the folder once for all the
    prefixes; cloud storages list each prefix on their side. An unknown storage
    yields nothing.

    :param storage: The storage to list.
    :param folder: The folder, e.g. `user_files`.
    :param name_prefixes: The starts of the file names, e.g. `tpl0000000012`.
    :return: The names, usable with the storage's other methods.
    """

    from storages.backends.azure_storage import AzureStorage
    from storages.backends.gcloud import GoogleCloudStorage
    from storages.backends.s3 import S3Storage
    from storages.utils import clean_name

    name_prefixes = tuple(name_prefixes)
    if not name_prefixes:
        return
    folder = folder.strip("/")

    if isinstance(storage, FileSystemStorage):
        try:
            with os.scandir(storage.path(folder)) as entries:
                for entry in entries:
                    if entry.name.startswith(name_prefixes) and entry.is_file():
                        yield posixpath.join(folder, entry.name)
        except FileNotFoundError:
            pass
        return

    if not storage_lists_by_prefix(storage):
        logger.warning(
            f"Listing files by prefix isn't supported by {type(storage).__name__}."
        )
        return

    for name_prefix in name_prefixes:
        relative = f"{folder}/{name_prefix}"
        if isinstance(storage, AzureStorage):
            prefix = storage._get_valid_path(relative)
        else:
            prefix = storage._normalize_name(clean_name(relative))
        root = prefix[: -len(relative)]
        if isinstance(storage, S3Storage):
            paginator = storage.connection.meta.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=storage.bucket_name, Prefix=prefix)
            keys = (
                entry["Key"] for page in pages for entry in page.get("Contents", ())
            )
        elif isinstance(storage, GoogleCloudStorage):
            keys = (blob.name for blob in storage.bucket.list_blobs(prefix=prefix))
        else:
            keys = (
                blob.name for blob in storage.client.list_blobs(name_starts_with=prefix)
            )

        for key in keys:
            name = key[len(root) :]
            if "/" not in name[len(folder) + 1 :]:
                yield name
