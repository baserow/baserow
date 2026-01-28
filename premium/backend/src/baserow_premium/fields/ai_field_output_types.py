import enum

from baserow.contrib.database.fields.field_types import (
    LongTextFieldType,
    SingleSelectFieldType,
)
from baserow.core.output_parsers import get_strict_enum_output_parser

from .registries import AIFieldOutputType


class TextAIFieldOutputType(AIFieldOutputType):
    type = "text"
    baserow_field_type = LongTextFieldType


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
        return get_strict_enum_output_parser(enum=choices)

    def format_prompt(self, prompt, ai_field):
        from langchain_core.prompts import PromptTemplate

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
        from langchain_core.exceptions import OutputParserException

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
