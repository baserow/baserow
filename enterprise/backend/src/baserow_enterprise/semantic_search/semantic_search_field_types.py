from typing import Any

from django.conf import settings
from django.db.models import QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry

from .registries import SemanticSearchFieldType

TEXT_FORMULA_TYPES = {"text", "char", "url"}


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

    def get_texts(self, field: Field, value: Any) -> list[str]:
        return [value[: get_max_characters_per_cell()]] if value else []


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
