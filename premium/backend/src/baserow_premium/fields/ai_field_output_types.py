from baserow.contrib.database.fields.field_types import (
    LongTextFieldType,
    SingleSelectFieldType,
)

from .registries import AIFieldOutputType


class TextAIFieldOutputType(AIFieldOutputType):
    type = "text"
    baserow_field_type = LongTextFieldType


class ChoiceAIFieldOutputType(AIFieldOutputType):
    type = "choice"
    baserow_field_type = SingleSelectFieldType

    def _find_select_option_by_value(self, value, ai_field):
        """Find the SelectOption whose value matches the given string."""

        try:
            return next(o for o in ai_field.select_options.all() if o.value == value)
        except StopIteration:
            return None

    def get_choices(self, ai_field):
        return [o.value for o in ai_field.select_options.all()]

    def resolve_choice(self, value, ai_field):
        if value is None:
            return None
        return self._find_select_option_by_value(value, ai_field)

    def prepare_data_sync_value(self, value, field, metadata):
        try:
            # The metadata contains a mapping of the select options where the key is the
            # old ID and the value is the new ID. For some reason the key is converted
            # to a string when moved into the JSON field.
            return int(metadata["select_options_mapping"][str(value)])
        except (KeyError, TypeError):
            return None
