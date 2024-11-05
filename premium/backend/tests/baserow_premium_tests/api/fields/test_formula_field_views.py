from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.generative_ai.registries import generative_ai_model_type_registry


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_without_license(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=False,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test",
            "ai_model": "test",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_table_does_not_exist(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": 0},
        ),
        {
            "ai_type": "test",
            "ai_model": "test",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_user_not_in_workspace(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    user_2, token_2 = premium_data_fixture.create_user_and_token(
        email="test2@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test_generative_ai",
            "ai_model": "model_1",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_generative_ai_does_not_exist(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "does_not_exist",
            "ai_model": "model_1",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_model_does_not_belong_to_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test_generative_ai",
            "ai_model": "does_not_exist",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_with_error(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test_generative_ai_prompt_error",
            "ai_model": "test_1",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GENERATIVE_AI_PROMPT"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_output_parser_error(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test_generative_ai",
            "ai_model": "test_1",
            "ai_prompt": "Generate a formula with all field types",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_OUTPUT_PARSER"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_invalid_request(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "",
            "ai_model": "",
            "ai_prompt": "",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": {
            "ai_type": [{"error": "This field may not be blank.", "code": "blank"}],
            "ai_model": [{"error": "This field may not be blank.", "code": "blank"}],
            "ai_prompt": [{"error": "This field may not be blank.", "code": "blank"}],
        },
    }


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
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
        response = api_client.post(
            reverse(
                "api:premium:fields:generate_ai_formula",
                kwargs={"table_id": table.id},
            ),
            {
                "ai_type": "test_generative_ai",
                "ai_model": "test_1",
                "ai_prompt": "Generate a formula with all field types",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        prompt = mock.call_args[0][1]
        temperature = mock.call_args[1]["temperature"]
        assert "You're a Baserow formula generator," in prompt
        assert f'"name": "{text_field.name}"' in prompt
        assert "Generate a formula with all field types" in prompt
        assert temperature is None

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"formula": "field()"}


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_with_temperature(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
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
        response = api_client.post(
            reverse(
                "api:premium:fields:generate_ai_formula",
                kwargs={"table_id": table.id},
            ),
            {
                "ai_type": "test_generative_ai",
                "ai_model": "test_1",
                "ai_prompt": "Generate a formula with all field types",
                "ai_temperature": 0.7,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        prompt = mock.call_args[0][1]
        temperature = mock.call_args[1]["temperature"]
        assert "You're a Baserow formula generator," in prompt
        assert f'"name": "{text_field.name}"' in prompt
        assert "Generate a formula with all field types" in prompt
        assert temperature == 0.7

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"formula": "field()"}


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_with_temperature_validation(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    response = api_client.post(
        reverse(
            "api:premium:fields:generate_ai_formula",
            kwargs={"table_id": table.id},
        ),
        {
            "ai_type": "test_generative_ai",
            "ai_model": "test_1",
            "ai_prompt": "Generate a formula with all field types",
            "ai_temperature": 3,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["ai_temperature"][0]["code"] == "max_value"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_formula_with_temperature_null(premium_data_fixture, api_client):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    generative_ai_instance = generative_ai_model_type_registry.get("test_generative_ai")

    with patch.object(
        generative_ai_instance, "prompt", return_value='{"formula": "field()"}'
    ) as mock:
        response = api_client.post(
            reverse(
                "api:premium:fields:generate_ai_formula",
                kwargs={"table_id": table.id},
            ),
            {
                "ai_type": "test_generative_ai",
                "ai_model": "test_1",
                "ai_prompt": "Generate a formula with all field types",
                "ai_temperature": None,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
