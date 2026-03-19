from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, Optional

from loguru import logger
from pydantic_ai.messages import UserContent

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel
    from baserow.core.generative_ai.registries import GenerativeAIModelType
    from baserow.core.models import Workspace
    from baserow_premium.fields.models import AIField


class AIFileManager:
    @staticmethod
    def prepare_file_content(
        ai_field: AIField,
        row: GeneratedTableModel,
        generative_ai_model_type: GenerativeAIModelType,
        workspace: Optional[Workspace] = None,
    ) -> tuple[list[UserContent], list[str]]:
        """
        Collect file metadata from the row's file field and let the model type
        decide which files to embed or upload. File data is only read from
        storage when the model type requests it.

        :param ai_field: The AI field that has an associated file field.
        :param row: The row to extract the files from.
        :param generative_ai_model_type: The model type that owns the file
            processing logic.
        :param workspace: Optional workspace for settings resolution.
        :return: Tuple of (content_parts, uploaded_file_ids_for_cleanup).
        """

        storage = get_default_storage()
        file_metas = AIFileManager._collect_file_metadata(ai_field, row, storage)

        def read_file(name: str) -> bytes:
            path = UserFileHandler().user_file_path(name)
            with storage.open(path, mode="rb") as f:
                return f.read()

        return generative_ai_model_type.prepare_files(file_metas, read_file, workspace)

    @staticmethod
    def _collect_file_metadata(
        ai_field: AIField,
        row: GeneratedTableModel,
        storage: object,
    ) -> list[tuple[str, int, str]]:
        """
        Return file metadata from the row's file field without reading data.

        :return: List of (name, size_bytes, media_type) tuples.
        """

        all_cell_files = getattr(row, f"field_{ai_field.ai_file_field_id}")
        if not isinstance(all_cell_files, list):
            all_cell_files = [all_cell_files] if all_cell_files else []

        result: list[tuple[str, int, str]] = []
        for file in all_cell_files:
            name = file["name"]
            file_path = UserFileHandler().user_file_path(name)

            try:
                size = storage.size(file_path)
            except (NotImplementedError, FileNotFoundError):
                continue

            media_type, _ = mimetypes.guess_type(name)
            if not media_type:
                media_type = "application/octet-stream"

            result.append((name, size, media_type))

        return result

    @staticmethod
    def delete_files(
        file_ids: list[str],
        generative_ai_model_type: GenerativeAIModelType,
        workspace: Optional[Workspace] = None,
    ) -> None:
        """
        Delete uploaded files from the provider.

        :param file_ids: List of provider file IDs to delete.
        :param generative_ai_model_type: The model type with delete_file() support.
        :param workspace: Optional workspace for settings resolution.
        """

        for file_id in file_ids:
            try:
                generative_ai_model_type.delete_file(file_id, workspace=workspace)
            except Exception:
                logger.warning(
                    f"Failed to delete file with ID {file_id} from provider {generative_ai_model_type.type}."
                )
