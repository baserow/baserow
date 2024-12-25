import hashlib
import mimetypes
import os
import pathlib
import re
import secrets
from io import BytesIO
from os.path import join
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from zipfile import ZipFile

from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.utils.http import parse_header_parameters

import advocate
from advocate.exceptions import UnacceptableAddressException
from loguru import logger
from PIL import Image, ImageOps
from requests.exceptions import RequestException

from baserow.core.import_export.utils import file_chunk_generator
from baserow.core.models import UserFile
from baserow.core.storage import (
    ExportZipFile,
    OverwritingStorageHandler,
    get_default_storage,
)
from baserow.core.utils import random_string, sha256_hash, stream_size, truncate_middle

from .exceptions import (
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
    InvalidFileStreamError,
    InvalidFileURLError,
    MaximumUniqueTriesError,
)

MIME_TYPE_UNKNOWN = "application/octet-stream"


class UserFileHandler:
    def get_user_file_by_name(
        self, user_file_name: str, base_queryset: Optional[QuerySet] = None
    ) -> UserFile:
        """
        Returns the user file with the provided id.

        :param user_file_name: The name of the user file.
        :param base_queryset: The base queryset that will be used to get the user file.
        :raises UserFile.DoesNotExist: If the user file does not exist.
        :return: The user file.
        """

        if base_queryset is None:
            base_queryset = UserFile.objects.all()

        return base_queryset.name(user_file_name).get()

    def user_file_path(self, user_file_name):
        """
        Generates the full user file path based on the provided file name. This path
        can be used with the storage.

        :param user_file_name: The user file name.
        :type user_file_name: str
        :return: The generated path.
        :rtype: str
        """

        if isinstance(user_file_name, UserFile):
            user_file_name = user_file_name.name

        return join(settings.USER_FILES_DIRECTORY, user_file_name)

    def user_file_sha256(self, user_file_name: str) -> str:
        """
        Extracts the sha256 hash from the user file name.

        :param user_file_name: The user file name
        :return The sha256 hexdigest.
        :raises ValueError: If the user file name does not contain a sha256 hash
        """

        sha256_hexdigest = os.path.splitext(user_file_name)[0].rsplit("_", 1)[-1]

        if not re.fullmatch(r"[a-fA-F0-9]{64}", sha256_hexdigest):
            raise ValueError("Incorrect user file name format.")

        return sha256_hexdigest

    def user_file_thumbnail_path(self, user_file_name, thumbnail_name):
        """
        Generates the full user file thumbnail path based on the provided filename.
        This path can be used with the storage.

        :param user_file_name: The user file name.
        :type user_file_name: str
        :param thumbnail_name: The thumbnail type name.
        :type thumbnail_name: str
        :return: The generated path.
        :rtype: str
        """

        if isinstance(user_file_name, UserFile):
            user_file_name = user_file_name.name

        return join(settings.USER_THUMBNAILS_DIRECTORY, thumbnail_name, user_file_name)

    def generate_unique(self, sha256_hash, extension, length=32, max_tries=1000):
        """
        Generates a unique nonexistent string for a new user file.

        :param sha256_hash: The hash of the file name. Needed because they are
            required to be unique together.
        :type sha256_hash: str
        :param extension: The extension of the file name. Needed because they are
            required to be unique together.
        :type extension: str
        :param length: Indicates the amount of characters that the unique must contain.
        :type length: int
        :param max_tries: The maximum amount of tries to check if a unique already
            exists.
        :type max_tries: int
        :raises MaximumUniqueTriesError: When the maximum amount of tries has
            been exceeded.
        :return: The generated unique string
        :rtype: str
        """

        i = 0

        while True:
            if i > max_tries:
                raise MaximumUniqueTriesError(
                    f"Tried {max_tries} tokens, but none of them are unique."
                )

            i += 1
            unique = random_string(length)

            if not UserFile.objects.filter(
                sha256_hash=sha256_hash, original_extension=extension, unique=unique
            ).exists():
                return unique

    def generate_and_save_image_thumbnails(
        self,
        image: Image,
        user_file_name: str,
        storage: Storage | None = None,
        only_with_name: str | None = None,
    ):
        """
        Generates the thumbnails based on the current settings and saves them to the
        provided storage. Note that existing files with the same name will be
        overwritten.

        :param image: The original Pillow image that serves as base when generating the
            image.
        :param user_file_name: The name of the user file that the thumbnail is for.
        :param storage: The storage where the thumbnails must be saved to.
        :param only_with_name: If provided, then only thumbnail types with that name
            will be regenerated.
        :raises ValueError: If the provided user file is not a valid image.
        """

        storage = storage or get_default_storage()
        image_width = image.width
        image_height = image.height

        for name, size in settings.USER_THUMBNAILS.items():
            if only_with_name and only_with_name != name:
                continue

            size_copy = size.copy()

            # If the width or height is None we want to keep the aspect ratio.
            if size_copy[0] is None and size_copy[1] is not None:
                size_copy[0] = round(image_width / image_height * size_copy[1])
            elif size_copy[1] is None and size_copy[0] is not None:
                size_copy[1] = round(image_height / image_width * size_copy[0])

            try:
                thumbnail = ImageOps.fit(image.copy(), size_copy, Image.LANCZOS)
            except OSError:
                pass
            else:
                thumbnail_stream = BytesIO()
                thumbnail.save(thumbnail_stream, image.format)
                thumbnail_stream.seek(0)
                thumbnail_path = self.user_file_thumbnail_path(user_file_name, name)

                handler = OverwritingStorageHandler(storage)
                handler.save(thumbnail_path, thumbnail_stream)

                del thumbnail
                del thumbnail_stream

    def upload_user_file(self, user, file_name, stream, storage=None):
        """
        Saves the provided uploaded file in the provided storage. If no storage is
        provided the default_storage will be used. An entry into the user file table
        is also created.

        :param user: The user on whose behalf the file is uploaded.
        :type user: User
        :param file_name: The provided file name when the file was uploaded.
        :type file_name: str
        :param stream: An IO stream containing the uploaded file.
        :type stream: IOBase
        :param storage: The storage where the file must be saved to.
        :type storage: Storage
        :raises InvalidFileStreamError: If the provided stream is invalid.
        :raises FileSizeToLargeError: If the provided content is too large.
        :return: The newly created user file.
        :rtype: UserFile
        """

        if not hasattr(stream, "read"):
            raise InvalidFileStreamError("The provided stream is not readable.")

        size = stream_size(stream)

        if size > settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB:
            raise FileSizeTooLargeError(
                settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB,
                "The provided file is too large.",
            )

        storage = storage or get_default_storage()
        stream_hash = sha256_hash(stream)
        file_name = truncate_middle(file_name, 64)

        existing_user_file = UserFile.objects.filter(
            original_name=file_name, sha256_hash=stream_hash
        ).first()

        if existing_user_file:
            return existing_user_file

        extension = pathlib.Path(file_name).suffix[1:].lower()
        mime_type = (
            mimetypes.guess_type(file_name)[0]
            or getattr(stream, "content_type", None)
            or MIME_TYPE_UNKNOWN
        )
        unique = self.generate_unique(stream_hash, extension)
        user_file = UserFile(
            original_name=file_name,
            original_extension=extension,
            size=size,
            mime_type=mime_type,
            unique=unique,
            uploaded_by=user,
            sha256_hash=stream_hash,
        )

        image = None
        try:
            image = Image.open(stream)
            user_file.mime_type = f"image/{image.format}".lower()
            self.generate_and_save_image_thumbnails(
                image, user_file.name, storage=storage
            )
            # Skip marking as images if thumbnails cannot be generated (i.e. PSD files).
            user_file.is_image = True
            user_file.image_width = image.width
            user_file.image_height = image.height
        except IOError:
            pass  # Not an image
        except Exception as exc:
            logger.warning(
                f"Failed to generate thumbnails for user file of type {mime_type}: {exc}"
            )
        finally:
            if image is not None:
                del image

        user_file.save()

        # Save the file to the storage.
        full_path = self.user_file_path(user_file)
        handler = OverwritingStorageHandler(storage)
        handler.save(full_path, stream)

        # Close the stream because we don't need it anymore.
        stream.close()

        return user_file

    def upload_user_file_by_url(self, user, url, storage=None):
        """
        Uploads a user file by downloading it from the provided URL.

        :param user: The user on whose behalf the file is uploaded.
        :type user: User
        :param url: The URL where the file must be downloaded from.
        :type url: str
        :param storage: The storage where the file must be saved to.
        :type storage: Storage
        :raises FileURLCouldNotBeReached: If the file could not be downloaded from
            the URL or if it points to an internal service.
        :raises InvalidFileURLError: If the provided file url is invalid.
        :return: The newly created user file.
        :rtype: UserFile
        """

        parsed_url = urlparse(url)

        if parsed_url.scheme not in ["http", "https"]:
            raise InvalidFileURLError("Only http and https are allowed.")

        # Pluck out the parsed URL path (in the event we've been given
        # a URL with a querystring) and then extract the filename.
        file_name = parsed_url.path.rstrip("/").split("/")[-1]
        try:
            response = advocate.get(url, stream=True, timeout=10)

            if not response.ok:
                raise FileURLCouldNotBeReached(
                    "The response did not respond with an " "OK status code."
                )

            try:
                content_length = int(response.headers.get("Content-Length", ""))
                if content_length > settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB:
                    raise FileSizeTooLargeError(
                        settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB,
                        "The provided file is too large.",
                    )
            except ValueError:
                pass

            content = b""
            for chunk in response.iter_content(chunk_size=None):
                content += chunk
                if len(content) > settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB:
                    response.close()
                    raise FileSizeTooLargeError(
                        settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB,
                        "The provided file is too large.",
                    )
            content_type = response.headers.get("Content-Type", "")

        except (RequestException, UnacceptableAddressException, ConnectionError):
            raise FileURLCouldNotBeReached("The provided URL could not be reached.")

        # content-type may contain extra params, like charset: text/plain; charset=utf-8
        if content_type:
            content_type, content_type_params = parse_header_parameters(content_type)

        # validate content_type value, reset to default if it's invalid
        if not content_type or (
            content_type and not mimetypes.guess_extension(content_type)
        ):
            content_type = MIME_TYPE_UNKNOWN

        # invalid file names which may be parsed from arbitrary url.
        # we need a replacement file name
        if file_name == "":
            ext = mimetypes.guess_extension(content_type) or ".bin"
            file_name_generator = hashlib.new("sha256")
            file_name_generator.update(
                bytes(f"{url} {secrets.token_urlsafe()}", "utf-8")
            )
            # generated file name is just a placeholder, we don't need to have full
            # hexdigest value
            file_name = f"{file_name_generator.hexdigest()[:12]}{ext}"

        file = SimpleUploadedFile(file_name, content, content_type=content_type)
        return self.upload_user_file(user, file_name, file, storage)

    def export_user_file(
        self,
        user_file: Optional[UserFile],
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Dict[str, Any] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Given a UserFile object, write it to files_zip so it can be exported
        and subsequently imported later.
        """

        if cache is None:
            cache = {}

        storage = storage or get_default_storage()

        if not user_file:
            return None

        name = user_file.name

        # Check if the user file object is already in the cache and if not,
        # it must be fetched and added to it.
        cache_entry = f"user_file_{name}"
        if cache_entry not in cache:
            namelist = (
                [item["name"] for item in files_zip.info_list()]
                if files_zip is not None
                else []
            )
            if files_zip is not None and name not in namelist:
                # Load the user file from the content and write it to the zip file
                # because it might not exist in the environment that it is going
                # to be imported in.
                file_path = self.user_file_path(name)

                chunk_generator = file_chunk_generator(storage, file_path)
                files_zip.add(chunk_generator, name)

            # Avoid writing the same file twice
            cache[cache_entry] = True

        return {"name": name, "original_name": user_file.original_name}

    def import_user_file(
        self,
        serialized_user_file: Dict[str, str],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Optional[UserFile]:
        """
        Given a valid file name and files_zip, re-create the file and return
        the resulting UserFile object.

        Otherwise, return the existing file from the db.
        """

        if not serialized_user_file:
            return None

        if files_zip is None:
            user_file = self.get_user_file_by_name(serialized_user_file["name"])
        else:
            name = serialized_user_file.get("name")
            original_name = serialized_user_file.get("original_name")
            if not name or not original_name:
                return None

            with files_zip.open(name) as stream:
                user_file = self.upload_user_file(
                    None, original_name, stream, storage=storage
                )

        return user_file
