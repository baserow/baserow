import shutil
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import IO, Any, Dict, Iterator, List

from django.core.files.storage import Storage

from baserow.core.user_files.handler import UserFileHandler

SPOOL_MAX_MEMORY_SIZE = 5 * 1024 * 1024


class TemplateFilesTransfer:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._names: Dict[str, None] = {}

    def add(self, _chunk_generator: Iterator[bytes], name: str) -> None:
        self._names[name] = None

    def info_list(self) -> List[Dict[str, str]]:
        return [{"name": name} for name in self._names]

    def open(self, name: str) -> IO[bytes]:
        """
        :param name: The name of the user file.
        :raises KeyError: If the name wasn't recorded or the file isn't stored.
        :return: A seekable copy of the file, closed by the caller.
        """

        if name not in self._names:
            raise KeyError(name)

        path = UserFileHandler().user_file_path(name)
        if not self.storage.exists(path):
            raise KeyError(name)

        spooled_file = SpooledTemporaryFile(max_size=SPOOL_MAX_MEMORY_SIZE)
        try:
            with self.storage.open(path, "rb") as stored_file:
                shutil.copyfileobj(stored_file, spooled_file)
        except FileNotFoundError as exc:
            spooled_file.close()
            raise KeyError(name) from exc
        except BaseException:
            spooled_file.close()
            raise

        spooled_file.seek(0)
        return spooled_file

    def close(self) -> None:
        pass


@dataclass(frozen=True)
class TemplateContent:
    applications: List[Dict[str, Any]]
    files: TemplateFilesTransfer
