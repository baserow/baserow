import mimetypes

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


class AIFileManager:
    @staticmethod
    def get_file_contents(ai_field, row, generative_ai_model_type):
        """
        Read compatible files from a row's file field and return them as
        pydantic-ai BinaryContent objects for multi-modal prompting.

        :param ai_field: The AI field that has an associated file field.
        :param row: The row to extract the files from.
        :param generative_ai_model_type: The model type used for compatibility
            checks (is_file_compatible, get_max_file_size).
        :return: A list of BinaryContent objects.
        """

        from pydantic_ai import BinaryContent

        storage = get_default_storage()

        all_cell_files = getattr(row, f"field_{ai_field.ai_file_field_id}")
        if not isinstance(all_cell_files, list):
            all_cell_files = [all_cell_files] if all_cell_files else []

        compatible_files = [
            file
            for file in all_cell_files
            if generative_ai_model_type.is_file_compatible(file["name"])
        ]

        max_file_size = generative_ai_model_type.get_max_file_size() * 1024 * 1024
        contents = []

        for file in compatible_files:
            file_path = UserFileHandler().user_file_path(file["name"])
            try:
                file_size = storage.size(file_path)
                if file_size > max_file_size:
                    continue
            except NotImplementedError:
                return []
            except FileNotFoundError:
                continue

            media_type, _ = mimetypes.guess_type(file["name"])
            if not media_type:
                media_type = "application/octet-stream"

            with storage.open(file_path, mode="rb") as storage_file:
                contents.append(
                    BinaryContent(data=storage_file.read(), media_type=media_type)
                )
                # For now only include first compatible file
                break

        return contents
