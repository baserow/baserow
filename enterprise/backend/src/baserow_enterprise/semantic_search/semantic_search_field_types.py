import time
from typing import Any

from django.conf import settings
from django.db.models import F, QuerySet

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.registries import file_text_extractor_registry

from .registries import SemanticSearchFieldType, SemanticSearchTexts

TEXT_FORMULA_TYPES = {"text", "char", "url"}
FILE_EXTRACTION_SECONDS_PER_CELL = 30


def get_max_characters_per_cell() -> int:
    """
    :return: The number of characters of a cell that fit in its chunks.
    """

    return (
        settings.BASEROW_SEMANTIC_SEARCH_CHUNK_SIZE
        * settings.BASEROW_SEMANTIC_SEARCH_MAX_CHUNKS_PER_CELL
    )


class TextSemanticSearchFieldTypeMixin:
    def get_values(self, field: Field, queryset: QuerySet) -> QuerySet:
        field_type = field_type_registry.get_by_model(field)
        return queryset.annotate(
            semantic_search_value=field_type.get_search_expression(field, queryset)
        ).values_list("id", "semantic_search_value")

    def get_texts(self, field: Field, value: Any) -> SemanticSearchTexts:
        return SemanticSearchTexts(
            [value[: get_max_characters_per_cell()]] if value else []
        )


class TextSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "text"


class LongTextSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "long_text"


class URLSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "url"


class EmailSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "email"


class PhoneNumberSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "phone_number"


class FormulaSemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "formula"

    def is_compatible(self, field: Field) -> bool:
        if field.formula_type == "array":
            return field.array_formula_type in TEXT_FORMULA_TYPES
        return field.formula_type in TEXT_FORMULA_TYPES


class LookupSemanticSearchFieldType(FormulaSemanticSearchFieldType):
    type = "lookup"


class RollupSemanticSearchFieldType(FormulaSemanticSearchFieldType):
    type = "rollup"


class AISemanticSearchFieldType(
    TextSemanticSearchFieldTypeMixin, SemanticSearchFieldType
):
    type = "ai"

    def is_compatible(self, field: Field) -> bool:
        from baserow_premium.fields.ai_field_output_types import (
            TextAIFieldOutputType,
        )

        return field.ai_output_type == TextAIFieldOutputType.type


class FileSemanticSearchFieldType(SemanticSearchFieldType):
    type = "file"

    def get_values(self, field: Field, queryset: QuerySet) -> QuerySet:
        # Only the metadata of the files is fetched. Because file names contain the
        # hash of the content, a cell only changes if its files change, so files are
        # only downloaded when needed.
        return queryset.annotate(semantic_search_value=F(field.db_column)).values_list(
            "id", "semantic_search_value"
        )

    def get_texts(self, field: Field, value: Any) -> SemanticSearchTexts:
        max_file_size = settings.BASEROW_SEMANTIC_SEARCH_MAX_FILE_SIZE_MB * 1024 * 1024
        # Text beyond what fits in the chunks of a cell isn't searchable, so files
        # aren't read anymore once it's reached.
        remaining_characters = get_max_characters_per_cell()
        # Bounds the time of a cell with many slow files, so that indexing it fits
        # in the time limit of the task.
        extraction_deadline = time.monotonic() + FILE_EXTRACTION_SECONDS_PER_CELL
        texts = []
        complete = True
        for file in (value or [])[
            : settings.BASEROW_SEMANTIC_SEARCH_MAX_FILES_PER_CELL
        ]:
            if remaining_characters <= 0:
                break
            visible_name = file.get("visible_name") or file["name"]
            content = None
            too_large = (file.get("size") or 0) > max_file_size
            remaining_seconds = extraction_deadline - time.monotonic()
            if not too_large and remaining_seconds <= 0:
                complete = False
            elif not too_large:
                try:
                    content = UserFileHandler().extract_text(
                        file["name"],
                        file.get("mime_type"),
                        remaining_characters,
                        timeout_seconds=remaining_seconds,
                    )
                except SoftTimeLimitExceeded:
                    raise
                except Exception as exc:  # noqa: BLE001
                    # A corrupt, unreadable or hostile file must not prevent the
                    # rest of the table from being indexed, so it's only searchable
                    # by its name until it's read again. Only the class is logged,
                    # because the details can contain file content.
                    logger.warning(
                        "Could not extract the text of file {}: {}",
                        file["name"],
                        exc.__class__.__name__,
                    )
                    complete = False
            text = f"{visible_name}\n\n{content}" if content else visible_name
            texts.append(text)
            remaining_characters -= len(text)
        return SemanticSearchTexts(texts, complete)

    def get_index_settings(self) -> list:
        return [
            settings.BASEROW_SEMANTIC_SEARCH_MAX_FILES_PER_CELL,
            settings.BASEROW_SEMANTIC_SEARCH_MAX_FILE_SIZE_MB,
            # Files of a newly supported type can be read now.
            sorted(file_text_extractor_registry.get_types()),
        ]
