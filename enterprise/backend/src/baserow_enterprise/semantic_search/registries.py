from typing import Any, NamedTuple, Optional

from django.db.models import QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.core.registry import Instance, Registry


class SemanticSearchTexts(NamedTuple):
    texts: list[str]
    # False if a part of the value couldn't be read, like a file of which the
    # storage was unavailable, so that the value is read again by a later update.
    complete: bool = True


class SemanticSearchFieldType(Instance):
    """
    Makes a field type compatible with semantic search. The `type` must match the
    type of the field type.
    """

    def is_compatible(self, field: Field) -> bool:
        """
        :param field: A field of the field type.
        :return: Whether its values can be searched, for example False for a
            formula of which the result isn't text.
        """

        return True

    def get_values(self, field: Field, queryset: QuerySet) -> QuerySet:
        """
        :param field: The field of which the values are read.
        :param queryset: The rows of which the values are read.
        :return: `(row_id, value)` pairs. The value must be cheap to compute because
            it decides whether a cell changed, before the more expensive `get_texts`
            is called.
        """

        raise NotImplementedError

    def get_texts(self, field: Field, value: Any) -> SemanticSearchTexts:
        """
        :param field: The field of the value.
        :param value: A value returned by `get_values`.
        :return: The texts that must be searchable.
        """

        raise NotImplementedError

    def get_index_settings(self) -> list:
        """
        :return: The settings that change the texts of the same value, so that all
            values are indexed again when they change.
        """

        return []


class SemanticSearchFieldTypeRegistry(Registry[SemanticSearchFieldType]):
    name = "semantic_search_field_type"

    def get_for_field(self, field: Field) -> Optional[SemanticSearchFieldType]:
        """
        :param field: The specific field that's checked.
        :return: The type that reads the texts of the field, or None if semantic
            search isn't supported for it.
        """

        field_type_name = field_type_registry.get_by_model(field).type
        semantic_search_field_type = self.registry.get(field_type_name)
        if semantic_search_field_type and semantic_search_field_type.is_compatible(
            field
        ):
            return semantic_search_field_type
        return None


semantic_search_field_type_registry = SemanticSearchFieldTypeRegistry()
