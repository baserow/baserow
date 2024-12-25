import enum
import json
from difflib import get_close_matches
from typing import Any

from langchain.output_parsers.enum import EnumOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import PromptTemplate

from baserow.contrib.database.fields.field_types import (
    LongTextFieldType,
    SingleSelectFieldType,
)

from .registries import AIFieldOutputType


class TextAIFieldOutputType(AIFieldOutputType):
    type = "text"
    baserow_field_type = LongTextFieldType


class StrictEnumOutputParser(EnumOutputParser):
    def get_format_instructions(self) -> str:
        json_array = json.dumps(self._valid_values)
        return f"""Categorize the result following these requirements:

- Select only one option from the JSON array below.
- Don't use quotes or commas or partial values, just the option name.
- Choose the option that most closely matches the row values.

```json
{json_array}
```"""  # nosec this falsely marks as hardcoded sql expression, but it's not related
        # to SQL at all.

    def parse(self, response: str) -> Any:
        response = response.strip()
        # Sometimes the LLM responds with a quotes value or with part of the value if
        # it contains a comma. Finding the close matches helps with selecting the
        # right value.
        closest_matches = get_close_matches(
            response, self._valid_values, n=1, cutoff=0.0
        )
        return super().parse(closest_matches[0])


class ChoiceAIFieldOutputType(AIFieldOutputType):
    type = "choice"
    baserow_field_type = SingleSelectFieldType

    def get_output_parser(self, ai_field):
        choices = enum.Enum(
            "Choices",
            {
                f"OPTION_{option.id}": option.value
                for option in ai_field.select_options.all()
            },
        )
        return StrictEnumOutputParser(enum=choices)

    def format_prompt(self, prompt, ai_field):
        output_parser = self.get_output_parser(ai_field)
        format_instructions = output_parser.get_format_instructions()
        prompt = PromptTemplate(
            template=prompt + "Given this user query: \n\n{format_instructions}",
            input_variables=[],
            partial_variables={"format_instructions": format_instructions},
        )
        message = prompt.format()
        return message

    def parse_output(self, output, ai_field):
        if not output:
            return None

        output_parser = self.get_output_parser(ai_field)
        try:
            parsed_output = output_parser.parse(output)
        except OutputParserException:
            return None
        select_option_id = int(parsed_output.name.split("_")[1])
        try:
            return next(
                o for o in ai_field.select_options.all() if o.id == select_option_id
            )
        except StopIteration:
            return None

    def prepare_data_sync_value(self, value, field, metadata):
        try:
            # The metadata contains a mapping of the select options where the key is the
            # old ID and the value is the new ID. For some reason the key is converted
            # to a string when moved into the JSON field.
            return int(metadata["select_options_mapping"][str(value)])
        except (KeyError, TypeError):
            return None
