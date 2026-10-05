from typing import TYPE_CHECKING, Any

from baserow.contrib.database.fields.field_types import (
    LongTextFieldType,
    SingleSelectFieldType,
)
from baserow.contrib.database.fields.rich_text_utils import (
    escape_user_file_references,
    strip_user_file_urls,
)

from .registries import AIFieldOutputType

if TYPE_CHECKING:
    from .models import AIField

# Tables are dropped when the rich text editor saves the cell.
RICH_TEXT_PROMPT_INSTRUCTIONS = (
    "Format with Markdown where helpful, but no tables, HTML or images."
)


class TextAIFieldOutputType(AIFieldOutputType):
    type = "text"
    baserow_field_type = LongTextFieldType

    def get_prompt_instructions(self, ai_field: "AIField") -> str | None:
        if ai_field.long_text_enable_rich_text:
            return RICH_TEXT_PROMPT_INSTRUCTIONS
        return None

    def sanitize_value(self, ai_field: "AIField", value: Any) -> Any:
        """
        Keeps user file images in a rich text value as literal text, because a rich
        text AI value never embeds one.

        :param ai_field: The AI field the value is stored in.
        :param value: The value to store.
        :return: The value with its user file images escaped.
        """

        if not ai_field.long_text_enable_rich_text or not value:
            return value
        return escape_user_file_references(strip_user_file_urls(value))


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
