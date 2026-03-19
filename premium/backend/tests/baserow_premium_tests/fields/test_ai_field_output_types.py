import enum
from difflib import get_close_matches

import pytest

from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.jobs.handler import JobHandler


def test_choice_fuzzy_matching():
    """Test that fuzzy matching correctly maps LLM text responses to enum values."""

    choices = enum.Enum(
        "Choices",
        {
            "OPTION_1": "Object",
            "OPTION_2": "Animal",
            "OPTION_3": "Human",
            "OPTION_4": "A,B,C",
        },
    )
    valid_values = [e.value for e in choices]

    def match(text):
        closest = get_close_matches(text.strip(), valid_values, n=1, cutoff=0.0)
        return choices(closest[0]) if closest else None

    assert match("Object") == choices.OPTION_1
    assert match("Animal") == choices.OPTION_2
    assert match("Human") == choices.OPTION_3
    assert match("A,B,C") == choices.OPTION_4

    # Fuzzy matching handles whitespace and quotes
    assert match(" Object ") == choices.OPTION_1
    assert match("'Object'") == choices.OPTION_1
    assert match("'A'") == choices.OPTION_4


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

        def prompt(
            self,
            model,
            prompt,
            workspace=None,
            temperature=None,
            settings_override=None,
            output_choices=None,
        ):
            self.i += 1
            if self.i == 1:
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
