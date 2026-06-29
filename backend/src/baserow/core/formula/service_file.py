from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError

from requests.exceptions import RequestException

import advocate
from advocate.exceptions import UnacceptableAddressException
from baserow.core.models import UserFile
from baserow.core.storage import get_default_storage
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
)
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import truncate_middle


@dataclass
class ServiceFile:
    """
    Normalized representation of a file value used by service formulas.

    A file can start as an uploaded stream, a serialized dictionary, an existing
    :class:`UserFile`, a storage URL, or a remote URL. The instance keeps the
    original metadata and lazily resolves the value to bytes or to a persisted
    user file only when a caller asks for it.
    """

    name: str
    visible_name: str = ""
    url: str = ""
    file: Any = None
    user_file: Optional[UserFile] = None
    mime_type: str = ""
    size: Optional[int] = None
    created_user_file: bool = False

    @classmethod
    def from_remote_url(cls, url: str) -> "ServiceFile":
        """
        Build a service file from an absolute HTTP(S) URL.
        """

        if not _is_remote_url(url):
            raise ValidationError("A valid file or url is required.")

        name = _file_name_from_url(url)
        return cls(name=name, visible_name=name, url=url)

    @classmethod
    def from_user_file(cls, user_file: UserFile) -> "ServiceFile":
        """
        Build a service file from an already persisted Baserow user file.
        """

        return cls(
            name=user_file.name,
            visible_name=user_file.original_name,
            url=UserFileHandler().get_user_file_url(user_file),
            user_file=user_file,
            mime_type=user_file.mime_type,
            size=user_file.size,
        )

    @classmethod
    def from_serialized(cls, value: dict) -> "ServiceFile":
        """
        Recreate a service file from the serialized shape used in formulas.

        The frontend and persisted service outputs can provide either
        ``visible_name`` or the older ``original_name`` key. When no explicit
        name is provided, the wrapped file object's name is used as a fallback.
        """

        name = value.get("name") or getattr(value.get("file"), "name", "")
        return cls(
            name=name,
            visible_name=value.get("visible_name")
            or value.get("original_name")
            or name,
            url=value.get("url", ""),
            file=value.get("file"),
            mime_type=value.get("mime_type", ""),
            size=value.get("size"),
        )

    def _has_readable_file(self) -> bool:
        """
        Return whether `self.file` is an actual readable stream.

        The `file` attribute can be populated from untrusted serialized payloads
        where it may end up being a placeholder (e.g. a string uid that was never
        resolved to an uploaded stream). In those cases we must ignore it and fall
        back to the other representations (user file, URL, name) instead of trying
        to read or upload a value that is not a stream.
        """

        return self.file is not None and hasattr(self.file, "read")

    def read_bytes(self) -> bytes:
        """
        Resolve this file value and return its content.

        The lookup order prefers in-memory uploaded files, then existing
        :class:`UserFile` objects, then local storage paths derived from the URL
        or file name, and finally remote HTTP(S) URLs. A ``ValidationError`` is
        raised when none of these representations can be read.
        """

        if self._has_readable_file() and not getattr(self.file, "closed", False):
            if hasattr(self.file, "seek"):
                self.file.seek(0)
            return self.file.read()

        if self.user_file is not None:
            storage = get_default_storage()
            path = UserFileHandler().user_file_path(self.user_file.name)
            with storage.open(path, "rb") as stream:
                return stream.read()

        if self.url:
            if storage_file := self._read_local_storage_file():
                return storage_file[1]

            if _is_remote_url(self.url):
                return _read_remote_url_bytes(self.url)

        if self.name and UserFileHandler().is_user_file_name(self.name):
            user_file = UserFileHandler().get_user_file_by_name(self.name)
            self.user_file = user_file
            storage = get_default_storage()
            path = UserFileHandler().user_file_path(user_file.name)
            with storage.open(path, "rb") as stream:
                return stream.read()

        raise ValidationError("A valid file or url is required.")

    def to_serialized(self) -> dict:
        """
        Convert this value to the ``__file__`` dictionary formula serializers use.

        The returned dictionary keeps enough metadata to display the file and to
        later resolve it again through :meth:`from_serialized`.
        """

        if self.user_file is not None:
            return {
                "__file__": True,
                "name": self.user_file.name,
                "visible_name": self.visible_name or self.user_file.original_name,
                "url": self.url or UserFileHandler().get_user_file_url(self.user_file),
                "mime_type": self.mime_type or self.user_file.mime_type,
                "size": self.size if self.size is not None else self.user_file.size,
            }

        name = self.name or getattr(self.file, "name", "")
        visible_name = self.visible_name or name
        mime_type = self.mime_type or getattr(self.file, "content_type", "")
        size = self.size
        if size is None:
            size = getattr(self.file, "size", None)

        return {
            "__file__": True,
            "name": name,
            "visible_name": visible_name,
            "url": self.url,
            "mime_type": mime_type,
            "size": size,
        }

    def to_user_file(self, user=None) -> UserFile:
        """
        Resolve this value to a persisted :class:`UserFile`.

        Uploaded streams and readable local storage paths are uploaded into the
        user-file storage. Existing user-file names and URLs are reused. Remote
        HTTP(S) URLs are fetched through ``UserFileHandler.upload_user_file_by_url``.
        The ``created_user_file`` flag is set when resolving this value creates a
        new user-file record instead of reusing an existing one.
        """

        if self.user_file is not None:
            return self.user_file

        handler = UserFileHandler()
        if self._has_readable_file():
            file_name = (
                self.visible_name or self.name or getattr(self.file, "name", "file")
            )
            self.user_file = self._upload_user_file(user, file_name, self.file)
            return self.user_file

        if self.url:
            user_file_name = _user_file_name_from_url(self.url)
            if user_file_name:
                self.user_file = handler.get_user_file_by_name(user_file_name)
                return self.user_file

            if storage_file := self._read_local_storage_file():
                path, content = storage_file
                self.user_file = self._upload_user_file(
                    user,
                    self.visible_name or self.name or path.rsplit("/", 1)[-1],
                    BytesIO(content),
                )
                return self.user_file

            if _is_remote_url(self.url):
                file_name = (
                    self.visible_name or self.name or _file_name_from_url(self.url)
                )
                existing_user_file_ids = set(
                    UserFile.objects.filter(
                        original_name=truncate_middle(file_name, 64),
                        deleted_at__isnull=True,
                    ).values_list("id", flat=True)
                )
                self.user_file = handler.upload_user_file_by_url(
                    user,
                    self.url,
                    file_name=file_name,
                )
                self.created_user_file = self.user_file.id not in existing_user_file_ids
                return self.user_file

            raise ValidationError("The file couldn't be read from storage.")

        if self.name and handler.is_user_file_name(self.name):
            self.user_file = handler.get_user_file_by_name(self.name)
            return self.user_file

        raise ValidationError("A valid file or url is required.")

    def _read_local_storage_file(self) -> Optional[tuple[str, bytes]]:
        """
        Return the local storage path and content represented by this file URL.
        """

        path = _storage_path_from_url(self.url, self.name)
        if not path:
            return None

        storage = get_default_storage()
        if not storage.exists(path):
            return None

        with storage.open(path, "rb") as stream:
            return path, stream.read()

    def _upload_user_file(self, user, file_name, stream) -> UserFile:
        """
        Upload a stream and track whether that upload created a new user file.
        """

        handler = UserFileHandler()
        existing_user_file_ids = set(
            UserFile.objects.filter(
                original_name=truncate_middle(file_name, 64),
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )
        user_file = handler.upload_user_file(user, file_name, stream)
        self.created_user_file = user_file.id not in existing_user_file_ids
        return user_file

    def to_file_field_dict(self, user=None) -> dict:
        """
        Convert this value to the dictionary accepted by Baserow file fields.
        """

        user_file = self.to_user_file(user)
        serialized = user_file.serialize()
        serialized["visible_name"] = self.visible_name or user_file.original_name
        return serialized


def _is_remote_url(value: str) -> bool:
    """
    Return whether the value is an absolute HTTP(S) URL.
    """

    parsed = urlparse(value)
    return parsed.scheme in ["http", "https"] and bool(parsed.netloc)


def _file_name_from_url(value: str) -> str:
    """
    Extract the final path segment from a URL, falling back to ``file``.
    """

    path_name = urlparse(value).path.rstrip("/").rsplit("/", 1)[-1]
    return path_name or "file"


def _user_file_name_from_url(url: str) -> Optional[str]:
    """
    Extract a Baserow user-file name from a URL when the path is a direct match.

    Lookalike URLs with extra path segments are rejected so remote URLs cannot be
    mistaken for local user files.
    """

    path = urlparse(url).path.lstrip("/")
    media_path = urlparse(settings.MEDIA_URL or "").path.strip("/")
    if media_path:
        media_prefix = f"{media_path}/"
        if path.startswith(media_prefix):
            path = path[len(media_prefix) :]

    user_files_prefix = f"{settings.USER_FILES_DIRECTORY.strip('/')}/"
    if not path.startswith(user_files_prefix):
        return None

    name = path[len(user_files_prefix) :].rstrip("/")
    if "/" not in name and name and UserFileHandler().is_user_file_name(name):
        return name
    return None


def _storage_path_from_url(url: str, name: str = "") -> str:
    """
    Convert a local media or user-file URL to the storage path it represents.

    When no local media prefix can be identified, the raw URL path is returned so
    callers can still check whether that path exists in the configured storage.
    """

    if user_file_name := _user_file_name_from_url(url):
        return UserFileHandler().user_file_path(user_file_name)

    path = urlparse(url).path.lstrip("/")
    media_url = urlparse(settings.MEDIA_URL or "").path.lstrip("/")
    if media_url and path.startswith(media_url):
        return path[len(media_url) :].lstrip("/")

    if name and UserFileHandler().is_user_file_name(name):
        return UserFileHandler().user_file_path(name)

    return path


def _read_remote_url_bytes(url: str) -> bytes:
    """
    Download a remote URL while applying Baserow's URL and file-size protections.
    """

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

        return content
    except (RequestException, UnacceptableAddressException, ConnectionError):
        raise FileURLCouldNotBeReached("The provided URL could not be reached.")
