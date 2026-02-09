from baserow.core.generative_ai.types import FileId
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


class AIFileManager:
    @staticmethod
    def upload_files_from_file_field(
        ai_field, row, generative_ai_model_type, workspace=None
    ) -> list[FileId]:
        """
        Collects files from a row cell stored in the associated file field
        and uploads them for generative AI model.

        :param ai_field: The AI field that has associated file field.
        :param row: The row to extract the files from.
        :param generative_ai_model_type: The model type to use for
            uploads.
        :param workspace: Optional workspace of the file field.
        """

        storage = get_default_storage()

        all_cell_files = getattr(row, f"field_{ai_field.ai_file_field_id}")
        if not isinstance(all_cell_files, list):
            # just a single file
            all_cell_files = [all_cell_files] if all_cell_files else []
        compatible_files = [
            file
            for file in all_cell_files
            if generative_ai_model_type.is_file_compatible(file["name"])
        ]
        file_ids: list[FileId] = []
        max_file_size = generative_ai_model_type.get_max_file_size() * 1024 * 1024
        for file in compatible_files:
            file_path = UserFileHandler().user_file_path(file["name"])
            try:
                file_size = storage.size(file_path)
                if file_size > max_file_size:
                    # skip files too large
                    continue
            except NotImplementedError:
                # The storage used doesn't support file sizes
                return []
            except FileNotFoundError:
                continue
            with storage.open(file_path, mode="rb") as storage_file:
                file_ids.append(
                    generative_ai_model_type.upload_file(
                        storage_file.name, storage_file.read(), workspace=workspace
                    )
                )
                # For now only uploading first file
                break
        return file_ids
