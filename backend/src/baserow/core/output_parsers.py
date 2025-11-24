import json
from difflib import get_close_matches
from typing import Any


def get_strict_enum_output_parser(enum: type) -> Any:
    from langchain.output_parsers.enum import EnumOutputParser

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
            # Sometimes the LLM responds with a quotes value or with part of the value
            # if it contains a comma. Finding the close matches helps with selecting the
            # right value.
            closest_matches = get_close_matches(
                response, self._valid_values, n=1, cutoff=0.0
            )
            return super().parse(closest_matches[0])

    return StrictEnumOutputParser(enum=enum)
