import json
from typing import Optional

from baserow_premium.fields.exceptions import AiFieldOutputParserException
from baserow_premium.prompts import get_generate_formula_prompt

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.models import Table
from baserow.core.db import specific_iterator
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry

from .pydantic_models import BaserowFormulaModel


class AIFieldHandler:
    @classmethod
    def generate_formula_with_ai(
        cls,
        table: Table,
        ai_type: str,
        ai_model: str,
        ai_prompt: str,
        ai_temperature: Optional[float] = None,
    ) -> str:
        """
        Generate a formula using the provided AI type, model and prompt.

        :param table: The table where to generate the formula for.
        :param ai_type: The generate AI type that must be used.
        :param ai_model: The model related to the AI type that must be used.
        :param ai_prompt: The prompt that must be executed.
        :param ai_temperature: The temperature that's passed into the prompt.
        :raises ModelDoesNotBelongToType: if the provided model doesn't belong to the
            type
        :return: The generated model.
        """

        from langchain_core.exceptions import OutputParserException
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import PromptTemplate

        generative_ai_model_type = generative_ai_model_type_registry.get(ai_type)
        ai_models = generative_ai_model_type.get_enabled_models(
            table.database.workspace
        )

        if ai_model not in ai_models:
            raise ModelDoesNotBelongToType(model_name=ai_model)

        table_schema = []
        for field in specific_iterator(table.field_set.all()):
            field_type = field_type_registry.get_by_model(field)
            table_schema.append(field_type.export_serialized(field))

        table_schema_json = json.dumps(table_schema, indent=4)
        output_parser = JsonOutputParser(pydantic_object=BaserowFormulaModel)
        format_instructions = output_parser.get_format_instructions()
        prompt = PromptTemplate(
            template=get_generate_formula_prompt() + "\n{format_instructions}",
            input_variables=["table_schema_json", "user_prompt"],
            partial_variables={"format_instructions": format_instructions},
        )
        message = prompt.format(
            table_schema_json=table_schema_json, user_prompt=ai_prompt
        )

        response = generative_ai_model_type.prompt(
            ai_model,
            message,
            workspace=table.database.workspace,
            temperature=ai_temperature,
        )
        try:
            return output_parser.parse(response)["formula"]
        except (OutputParserException, TypeError) as e:
            raise AiFieldOutputParserException(
                "The model didn't respond with the correct output. " "Please try again."
            ) from e
