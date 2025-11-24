import enum

import pytest
from baserow_premium.fields.ai_field_output_types import get_strict_enum_output_parser
from langchain_core.prompts import PromptTemplate

from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.jobs.handler import JobHandler


def test_strict_enum_output_parser():
    choices = enum.Enum(
        "Choices",
        {
            "OPTION_1": "Object",
            "OPTION_2": "Animal",
            "OPTION_3": "Human",
            "OPTION_4": "A,B,C",
        },
    )
    output_parser = get_strict_enum_output_parser(enum=choices)
    format_instructions = output_parser.get_format_instructions()
    prompt = "What is a motorcycle?"
    prompt = PromptTemplate(
        template=prompt + "\n\n{format_instructions}",
        input_variables=[],
        partial_variables={"format_instructions": format_instructions},
    )
    message = prompt.format()

    assert '["Object", "Animal", "Human", "A,B,C"]' in message

    assert output_parser.parse("Object") == choices.OPTION_1
    assert output_parser.parse("Animal") == choices.OPTION_2
    assert output_parser.parse("Human") == choices.OPTION_3
    assert output_parser.parse("A,B,C") == choices.OPTION_4

    assert output_parser.parse(" Object ") == choices.OPTION_1
    assert output_parser.parse("'Object'") == choices.OPTION_1
    assert output_parser.parse("'A'") == choices.OPTION_4


@pytest.mark.django_db
@pytest.mark.field_ai
def test_choice_output_type(premium_data_fixture, api_client):
    class TestAIChoiceOutputTypeGenerativeAIModelType(GenerativeAIModelType):
        type = "test_ai_choice_ouput_type"
        i = 0

        def is_enabled(self, workspace=None):
            return True

        def get_enabled_models(self, workspace=None):
            return ["test_1"]

        def prompt(self, model, prompt, workspace=None, temperature=None):
            self.i += 1
            if self.i == 1:
                # Existing option should be matches based on the string.
                return "Object"
            else:
                return "Else"

        def get_settings_serializer(self):
            return None

    generative_ai_model_type_registry.register(
        TestAIChoiceOutputTypeGenerativeAIModelType()
    )

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_ai_field(
        table=table,
        order=0,
        name="ai",
        ai_output_type="choice",
        ai_generative_ai_type="test_ai_choice_ouput_type",
        ai_generative_ai_model="test_1",
        ai_prompt="'Option'",
    )
    option_1 = premium_data_fixture.create_select_option(
        field=field, value="Object", color="red"
    )
    option_2 = premium_data_fixture.create_select_option(
        field=field, value="Else", color="red"
    )
    premium_data_fixture.create_select_option(field=field, value="Animal", color="blue")

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        sync=True,
        field_id=field.id,
        row_ids=[row_1.id, row_2.id],
    )

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    assert getattr(row_1, f"field_{field.id}").id == option_1.id
    assert getattr(row_2, f"field_{field.id}").id == option_2.id
