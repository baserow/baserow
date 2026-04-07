from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


@dataclass
class AIFile:
    """
    Lightweight wrapper around a serialized UserFile dict from a file field
    cell. Provides lazy file reading via :meth:`read_content`.

    After :meth:`GenerativeAIModelType.prepare_files`, accepted files have
    ``content`` set (the pydantic-ai content part for the prompt) and
    optionally ``provider_file_id`` (if the file was uploaded to the
    provider and needs cleanup).
    """

    name: str
    original_name: str
    size: int
    mime_type: str

    # Set by model_type.prepare_files():
    content: Optional[UserContent] = field(default=None, repr=False)
    provider_file_id: Optional[str] = None

    @property
    def file_path(self) -> str:
        return UserFileHandler().user_file_path(self.name)

    def read_content(self) -> bytes:
        storage = get_default_storage()
        with storage.open(self.file_path, mode="rb") as f:
            return f.read()
