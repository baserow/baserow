from unittest.mock import patch

import pytest
from baserow_premium.fields.exceptions import AiFieldOutputParserException
from baserow_premium.fields.handler import AIFieldHandler

from baserow.core.generative_ai.exceptions import (
    GenerativeAITypeDoesNotExist,
    ModelDoesNotBelongToType,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry


@pytest.mark.django_db
@pytest.mark.field_ai
def test_generate_formula_generative_ai_does_not_exist(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    with pytest.raises(GenerativeAITypeDoesNotExist):
        AIFieldHandler.generate_formula_with_ai(
            table,
            "does_not_exist",
            "model_1",
            "Generate a formula with all field types",
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_generate_formula_model_does_not_belong_to_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    with pytest.raises(ModelDoesNotBelongToType):
        AIFieldHandler.generate_formula_with_ai(
            table,
            "test_generative_ai",
            "does_not_exist",
            "Generate a formula with all field types",
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_generate_formula_output_parser_error(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    with pytest.raises(AiFieldOutputParserException):
        AIFieldHandler.generate_formula_with_ai(
            table,
            "test_generative_ai",
            "test_1",
            "Generate a formula with all field types",
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_generate_formula(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table)

    generative_ai_instance = generative_ai_model_type_registry.get("test_generative_ai")

    with patch.object(
        generative_ai_instance, "prompt", return_value='{"formula": "field()"}'
    ) as mock:
        formula = AIFieldHandler.generate_formula_with_ai(
            table,
            "test_generative_ai",
            "test_1",
            "Generate a formula with all field types",
        )

        prompt = mock.call_args[0][1]
        assert "You're a Baserow formula generator," in prompt
        assert f'"name": "{text_field.name}"' in prompt
        assert "Generate a formula with all field types" in prompt
        assert formula == "field()"
