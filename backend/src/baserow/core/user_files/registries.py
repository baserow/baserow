from typing import IO, Optional

from baserow.core.registry import Instance, Registry


class FileTextExtractorType(Instance):
    def can_extract(self, mime_type: str, file_name: str) -> bool:
        """
        :param mime_type: The lowercase mime type of the file.
        :param file_name: The lowercase name of the file.
        :return: Whether the text of the file can be extracted.
        """

        raise NotImplementedError

    def extract(self, file: IO[bytes], max_characters: int) -> str:
        """
        :param file: The opened file.
        :param max_characters: The maximum length of the text. The file is only
            read as far as needed for it.
        :return: The text of the file.
        :raises Exception: Any exception of reading a corrupt or unsupported file.
        """

        raise NotImplementedError


class FileTextExtractorRegistry(Registry[FileTextExtractorType]):
    name = "file_text_extractor"

    def get_for_file(
        self, mime_type: str, file_name: str
    ) -> Optional[FileTextExtractorType]:
        """
        :param mime_type: The mime type of the file.
        :param file_name: The name of the file.
        :return: The extractor that supports the file, if any.
        """

        mime_type = (mime_type or "").lower()
        file_name = (file_name or "").lower()
        return next(
            (
                extractor
                for extractor in self.get_all()
                if extractor.can_extract(mime_type, file_name)
            ),
            None,
        )


file_text_extractor_registry = FileTextExtractorRegistry()
