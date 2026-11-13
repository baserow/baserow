import hashlib
import mimetypes
import os
import pathlib
import re
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from io import BytesIO
from os.path import join
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from zipfile import ZipFile

from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from django.utils.http import parse_header_parameters

from loguru import logger
from requests.exceptions import RequestException

import advocate
from advocate.exceptions import UnacceptableAddressException
from baserow.core.import_export.utils import file_chunk_generator
from baserow.core.models import UserFile
from baserow.core.storage import (
    ExportZipFile,
    OverwritingStorageHandler,
    get_default_storage,
)
from baserow.core.utils import random_string, sha256_hash, stream_size, truncate_middle

from .exceptions import (
    ActiveContentBlockedUserFileError,
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
    InvalidFileStreamError,
    InvalidFileURLError,
    MaximumUniqueTriesError,
)
from .models import deconstruct_user_file_regex
from .template_files import (
    TEMPLATE_FILE_PREFIX,
    get_template_file_owner,
    template_file_prefix,
)

if TYPE_CHECKING:
    from PIL import Image

_new_stored_files: ContextVar[Optional[List[Tuple[str, Storage]]]] = ContextVar(
    "new_stored_files", default=None
)

MIME_TYPE_UNKNOWN = "application/octet-stream"
ACTIVE_CONTENT_EXTENSIONS = {"html", "htm", "xhtml", "xml", "svg", "svgz"}
ACTIVE_CONTENT_MIME_TYPES = {
    "application/xhtml+xml",
    "application/xml",
    "image/svg+xml",
    "text/html",
    "text/xml",
}


class UserFileHandler:
    def _is_active_content_extension(self, extension: str) -> bool:
        return extension.lower() in ACTIVE_CONTENT_EXTENSIONS

    def _is_active_content_mime_type(self, mime_type: str) -> bool:
        return mime_type.lower() in ACTIVE_CONTENT_MIME_TYPES

    def _resolve_mime_type_and_active_content(
        self, file_name: str, extension: str, stream
    ) -> tuple[str, bool]:
        """
        Resolves the MIME type for an uploaded file and decides whether it should be
        treated as active content.

        Both the filename-derived MIME type and the client-supplied `content_type` are
        checked independently against the active-content blocklist so that a malicious
        client cannot bypass the gate by pairing an innocuous extension with a dangerous
        Content-Type header (or vice versa).

        :param file_name: The name of the uploaded file.
        :param extension: The file extension of the uploaded file.
        :param stream: The file content stream of the uploaded file, which may have a
            `content_type` attribute.
        :return: A tuple of the resolved MIME type and whether the file is considered
            active content.
        """

        guessed_mime_type = mimetypes.guess_type(file_name)[0]
        uploaded_mime_type = getattr(stream, "content_type", None)
        mime_type = guessed_mime_type or uploaded_mime_type or MIME_TYPE_UNKNOWN
        is_active_content = (
            self._is_active_content_extension(extension)
            or (
                guessed_mime_type is not None
                and self._is_active_content_mime_type(guessed_mime_type)
            )
            or (
                uploaded_mime_type is not None
                and self._is_active_content_mime_type(uploaded_mime_type)
            )
        )
        return mime_type, is_active_content

    def _neutralize_active_content(self, user_file: UserFile) -> UserFile:
        user_file.mime_type = MIME_TYPE_UNKNOWN
        user_file.is_image = False
        user_file.image_width = None
        user_file.image_height = None
        return user_file

    def is_user_file_name(self, user_file_name: str) -> bool:
        """
        Checks if the given name is a user file name.
        """

        matches = deconstruct_user_file_regex.match(user_file_name)
        return bool(matches)

    def get_user_file_url(self, user_file):
        """Returns user file url"""

        storage = get_default_storage()
        name = user_file.name
        path = UserFileHandler().user_file_path(name)
        url = storage.url(path)
        return url

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

    def generate_unique(
        self, sha256_hash, extension, length=32, max_tries=1000, prefix=""
    ):
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
        :param prefix: The fixed start of the unique, counted in `length`.
        :type prefix: str
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
            unique = prefix + random_string(length - len(prefix))

            if not prefix and unique.startswith(TEMPLATE_FILE_PREFIX):
                continue

            if not UserFile.objects.filter(
                sha256_hash=sha256_hash, original_extension=extension, unique=unique
            ).exists():
                return unique

    def generate_and_save_image_thumbnails(
        self,
        image: "Image",
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

        from PIL import Image, ImageOps

        storage = storage or get_default_storage()

        # adjust image orientation, if exif data differs from the image data
        try:
            ImageOps.exif_transpose(image, in_place=True)
        # ignore cases of incomplete images
        except OSError:
            pass

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

        from PIL import Image

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
        extension = pathlib.Path(file_name).suffix[1:].lower()
        mime_type, is_active_content = self._resolve_mime_type_and_active_content(
            file_name, extension, stream
        )

        if is_active_content and settings.FILE_UPLOAD_ACTIVE_CONTENT_POLICY == "block":
            raise ActiveContentBlockedUserFileError(
                "The provided file type is not allowed."
            )

        template_workspace_id = get_template_file_owner()
        existing_user_files = UserFile.objects.filter(
            original_name=file_name,
            sha256_hash=stream_hash,
            deleted_at__isnull=True,
        )
        if template_workspace_id is None:
            existing_user_files = existing_user_files.exclude_template_files()
            unique_prefix = ""
        else:
            existing_user_files = existing_user_files.template_files(
                template_workspace_id
            )
            unique_prefix = template_file_prefix(template_workspace_id)
        existing_user_file = next(iter(existing_user_files.order_by()[:1]), None)

        if existing_user_file:
            if is_active_content:
                self._neutralize_active_content(existing_user_file)
                existing_user_file.save(
                    update_fields=[
                        "mime_type",
                        "is_image",
                        "image_width",
                        "image_height",
                    ]
                )
            return existing_user_file

        unique = self.generate_unique(stream_hash, extension, prefix=unique_prefix)
        user_file = UserFile(
            original_name=file_name,
            original_extension=extension,
            size=size,
            mime_type=mime_type,
            unique=unique,
            uploaded_by=user,
            sha256_hash=stream_hash,
        )
        new_stored_files = _new_stored_files.get()
        if new_stored_files is not None:
            new_stored_files.append((user_file.name, storage))

        if is_active_content:
            self._neutralize_active_content(user_file)
        else:
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
                    f"Failed to generate thumbnails for user file of type "
                    f"{mime_type}: {exc}"
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

    def upload_user_file_by_url(self, user, url, file_name=None, storage=None):
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
        file_name = (
            parsed_url.path.rstrip("/").split("/")[-1]
            if file_name is None
            else file_name
        )

        try:
            response = advocate.get(url, stream=True, timeout=10)

            if not response.ok:
                raise FileURLCouldNotBeReached(
                    "The response did not respond with an OK status code."
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

    def add_user_file_to_export(
        self,
        name: str,
        files_zip: ExportZipFile,
        storage: Storage,
        cache: Dict[str, Any],
        zip_name: Optional[str] = None,
        skip_missing: bool = False,
    ) -> bool:
        """
        Adds the stored user file to the export zip, unless the zip already holds a
        member with that name. The names in the zip are tracked in the export cache,
        so every exporter sharing the cache adds each file at most once.

        :param name: The name of the user file to add.
        :param files_zip: The zip the export is written to.
        :param storage: The storage the user file is read from.
        :param cache: The export cache shared by the exporters of the export.
        :param zip_name: The member name in the zip, `name` by default.
        :param skip_missing: Leave out a file missing from the storage instead of
            failing the export when the zip is streamed.
        :return: Whether the zip holds the file.
        """

        zip_names = cache.get("_zip_names")
        if zip_names is None:
            zip_names = {item["name"] for item in files_zip.info_list()}
            cache["_zip_names"] = zip_names

        zip_name = zip_name or name
        if zip_name in zip_names:
            return True

        file_path = self.user_file_path(name)
        if skip_missing:
            missing_files = cache.setdefault("_missing_user_files", set())
            if name in missing_files:
                return False
            if not storage.exists(file_path):
                missing_files.add(name)
                return False

        files_zip.add(file_chunk_generator(storage, file_path), zip_name)
        zip_names.add(zip_name)
        return True

    def delete_user_file_from_storage(
        self, user_file_name: str | UserFile, storage: Storage
    ) -> List[str]:
        """
        Deletes the stored file of a user file and its thumbnails.

        :param user_file_name: The user file or its name.
        :param storage: The storage holding the file.
        :return: The paths that existed and were deleted.
        """

        paths = [self.user_file_path(user_file_name)] + [
            self.user_file_thumbnail_path(user_file_name, thumbnail_name)
            for thumbnail_name in settings.USER_THUMBNAILS
        ]
        deleted_paths = []
        for path in paths:
            if storage.exists(path):
                storage.delete(path)
                deleted_paths.append(path)
        return deleted_paths

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

        if not user_file:
            return None

        if files_zip is not None:
            self.add_user_file_to_export(
                user_file.name,
                files_zip,
                storage or get_default_storage(),
                {} if cache is None else cache,
            )

        return {"name": user_file.name, "original_name": user_file.original_name}

    def import_user_file(
        self,
        serialized_user_file: Dict[str, str],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Optional[UserFile]:
        """
        Re-creates the file from files_zip and returns the resulting UserFile, or None
        when the zip lacks it. Without a files zip, returns the existing file by name.
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

            try:
                stream = files_zip.open(name)
            except KeyError:
                return None
            with stream as file:
                user_file = self.upload_user_file(
                    None, original_name, file, storage=storage
                )

        return user_file


@contextmanager
def delete_new_files_on_error():
    """
    Records the user files `upload_user_file` newly stores inside the block. When
    the block raises, deletes those of them no `UserFile` row references, with
    their thumbnails, and re-raises. Open it outside the transaction the uploads
    run in, so the rows are rolled back before the check.
    """

    new_stored_files = []
    token = _new_stored_files.set(new_stored_files)
    try:
        yield
    except BaseException:
        try:
            _delete_unreferenced_files(new_stored_files)
        except Exception:
            logger.exception("Could not delete the new files of a failed operation.")
        raise
    finally:
        _new_stored_files.reset(token)


def _delete_unreferenced_files(stored_files: List[Tuple[str, Storage]]):
    if not stored_files:
        return

    referenced = {
        user_file.name
        for user_file in UserFile.objects.all().name(
            *{name for name, _ in stored_files}
        )
    }
    handler = UserFileHandler()
    for name, storage in stored_files:
        if name not in referenced:
            handler.delete_user_file_from_storage(name, storage)
