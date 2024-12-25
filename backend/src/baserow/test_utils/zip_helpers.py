"""
This module provides utility functions for manipulating ZIP files.
"""

import zipfile
from typing import AnyStr, Optional


def remove_file_from_zip(zip_path: str, new_zip_path: str, file_to_remove: str) -> str:
    """
    Removes a specific file from a ZIP archive and creates a new ZIP archive
    without that file.

    :param zip_path: The path to the original ZIP file.
    :param new_zip_path: The path where the new ZIP file will be created.
    :param file_to_remove: The name of the file to be removed from the ZIP archive.
    :return: The path to the new ZIP file.
    """

    with zipfile.ZipFile(zip_path, "r") as original_zip:
        with zipfile.ZipFile(new_zip_path, "w") as temp_zip:
            for item in original_zip.infolist():
                if item.filename != file_to_remove:
                    temp_zip.writestr(item, original_zip.read(item.filename))

    return new_zip_path


def get_file_content_from_zip(zip_path: str, file_to_get: str) -> Optional[AnyStr]:
    """
    Retrieves the content of a specific file from a ZIP archive.

    :param zip_path: The path to the ZIP file.
    :param file_to_get: The name of the file whose content is to be retrieved.
    :return: The content of the file as bytes, or None if the file is not found.
    """

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        try:
            with zip_file.open(file_to_get) as file:
                return file.read()
        except KeyError:
            return None


def change_file_content_in_zip(
    zip_path: str, new_zip_path: str, file_to_change: str, new_content: AnyStr
) -> str:
    """
    Changes the content of a specific file in a ZIP archive and creates a new ZIP
    archive with the updated content.

    :param zip_path: The path to the original ZIP file.
    :param new_zip_path: The path where the new ZIP file will be created.
    :param file_to_change: The name of the file whose content is to be changed.
    :param new_content: The new content to write to the file.
    :return: The path to the new ZIP file.
    """

    with zipfile.ZipFile(zip_path, "r") as original_zip:
        with zipfile.ZipFile(new_zip_path, "w") as temp_zip:
            for item in original_zip.infolist():
                if item.filename == file_to_change:
                    temp_zip.writestr(file_to_change, new_content)
                else:
                    temp_zip.writestr(item, original_zip.read(item.filename))

    return new_zip_path


def add_file_to_zip(
    zip_path: str, new_zip_path: str, file_name: str, content: bytes
) -> str:
    """
    Adds a specific file with content to a ZIP archive and creates a new ZIP archive
    with that file added.

    :param zip_path: The path to the original ZIP file.
    :param new_zip_path: The path where the new ZIP file will be created.
    :param file_name: The name of the file to be added to the ZIP archive.
    :param content: The content to be written to the file as bytes.
    :return: The path to the new ZIP file.
    """

    with zipfile.ZipFile(zip_path, "r") as original_zip:
        with zipfile.ZipFile(new_zip_path, "w") as temp_zip:
            for item in original_zip.infolist():
                temp_zip.writestr(item, original_zip.read(item.filename))
            temp_zip.writestr(file_name, content)

    return new_zip_path
