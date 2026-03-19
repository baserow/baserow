import json
from difflib import get_close_matches

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

    def format_prompt(self, prompt, ai_field):
        """Add choice instructions to the prompt for the prompt_with_files path."""

        options = [o.value for o in ai_field.select_options.all()]
        json_array = json.dumps(options)
        instructions = f"""Categorize the result following these requirements:

    - Select only one option from the JSON array below.
    - Don't use quotes or commas or partial values, just the option name.
    - Choose the option that most closely matches the row values.

```json
{json_array}
```"""  # noqa: S608 - not SQL, just a JSON template
        return prompt + "Given this user query: \n\n" + instructions

    def parse_output(self, output, ai_field):
        """Parse text output to a SelectOption using fuzzy matching.

        Used in the prompt_with_files fallback path.
        """

        if not output:
            return None

        valid_values = [o.value for o in ai_field.select_options.all()]
        closest = get_close_matches(output.strip(), valid_values, n=1, cutoff=0.6)
        if not closest:
            return None
        return self._find_select_option_by_value(closest[0], ai_field)

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
