from django.shortcuts import reverse

import pytest
from baserow_premium.fields.field_types import AIFieldType
from baserow_premium.fields.models import AIField
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    handler = FieldHandler()
    ai_field = handler.create_field(
        user=user,
        table=table,
        type_name="ai",
        name="ai_1",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'Who are you?'",
    )

    assert ai_field.ai_output_type == "text"  # default value
    assert ai_field.ai_generative_ai_type == "test_generative_ai"
    assert ai_field.ai_generative_ai_model == "test_1"
    assert ai_field.ai_prompt["formula"] == "'Who are you?'"
    assert len(AIField.objects.all()) == 1


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")

    handler = FieldHandler()
    ai_field = handler.update_field(
        user=user,
        field=field,
        name="ai_1",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'Who are you?'",
    )

    assert ai_field.ai_output_type == "text"  # default value
    assert ai_field.ai_generative_ai_type == "test_generative_ai"
    assert ai_field.ai_generative_ai_model == "test_1"
    assert ai_field.ai_prompt["formula"] == "'Who are you?'"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_delete_ai_field_type(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="name",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'Who are you?'",
    )

    handler = FieldHandler()
    handler.delete_field(user=user, field=field)

    assert len(AIField.objects.all()) == 0


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "text"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert response_json["ai_temperature"] is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_with_non_existing_ai_output_type(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_output_type": "DOES_NOT_EXIST",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ai_output_type"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_with_ai_output_type(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_output_type": "text",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "text"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert response_json["ai_temperature"] is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_with_temperature_via_api(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
            "ai_temperature": 0.7,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert response_json["ai_temperature"] == 0.7


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_with_temperature_validations_via_api(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
            "ai_temperature": 3,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ai_temperature"][0]["code"] == "max_value"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
            "ai_temperature": -1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ai_temperature"][0]["code"] == "min_value"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_temperature_none_via_api(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(
        table=table, order=1, name="name", ai_temperature=0.7
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_temperature": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["ai_temperature"] is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_via_api_invalid_output_type(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(
        table=table, order=1, name="name", ai_temperature=0.7
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_output_type": "INVALID_CHOICE",
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_temperature": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ai_output_type"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_via_api_valid_output_type(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(
        table=table, order=1, name="name", ai_temperature=0.7
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_output_type": "text",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_temperature": None,
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "text"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert response_json["ai_temperature"] is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_to_ai_field_with_all_parameters(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "type": "ai",
            "ai_output_type": "text",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_temperature": None,
            "ai_prompt": "'Who are you?'",
            "ai_auto_update": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "text"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert response_json["ai_temperature"] is None
    assert response_json["ai_auto_update"] is True


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_to_ai_field_without_parameters(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "text"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == ""
    assert response_json["ai_temperature"] is None
    assert response_json["ai_auto_update"] is False


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_invalid_formula(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "ffff;;s9(",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ai_prompt"][0]["code"] == "invalid"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_with_invalid_type(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "does_not_exist",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_with_invalid_model(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "does_not_exist",
            "ai_prompt": "'Who are you?'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_with_invalid_type(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"ai_generative_ai_type": "does_not_exist"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_with_invalid_model(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"ai_generative_ai_model": "does_not_exist"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_with_valid_model(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"ai_generative_ai_model": "test_1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"ai_generative_ai_type": "test_generative_ai"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_file_field_compatible(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")
    file_field = premium_data_fixture.create_file_field(
        table=table, order=2, name="file"
    )

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Test'",
            "ai_file_field_id": file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_file_field_not_compatible(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")
    file_field = premium_data_fixture.create_file_field(
        table=table, order=2, name="file"
    )

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Test'",
            "ai_file_field_id": file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_SUPPORT_FILE_FIELD"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_type_via_api_file_field_doesnt_exist(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Test'",
            "ai_file_field_id": 999,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json
    assert response_json["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_file_field_compatible(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")
    file_field = premium_data_fixture.create_file_field(
        table=table, order=2, name="file"
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_file_field_id": file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_file_field_not_compatible(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")
    file_field = premium_data_fixture.create_file_field(
        table=table, order=2, name="file"
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_file_field_id": file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_SUPPORT_FILE_FIELD"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_update_ai_field_type_via_api_file_field_doesnt_exist(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    field = premium_data_fixture.create_ai_field(table=table, order=1, name="name")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {
            "ai_generative_ai_type": "test_generative_ai_with_files",
            "ai_generative_ai_model": "test_1",
            "ai_file_field_id": 999999999,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json
    assert response_json["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_duplicate_table_with_ai_field(premium_data_fixture):
    session_id = "session-id"
    user = premium_data_fixture.create_user(session_id=session_id)
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="text"
    )
    file_field = premium_data_fixture.create_file_field(
        table=table, order=1, name="file"
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=2,
        name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=file_field,
        ai_prompt=f"concat('test:',get('fields.field_{text_field.id}'))",
    )

    table_handler = TableHandler()
    duplicated_table = table_handler.duplicate_table(user, table)
    duplicated_fields = specific_iterator(
        duplicated_table.field_set.all().order_by("id")
    )
    duplicated_text_field = duplicated_fields[0]
    duplicated_file_field = duplicated_fields[1]
    duplicated_ai_field = duplicated_fields[2]

    assert duplicated_ai_field.name == "ai"
    assert duplicated_ai_field.ai_generative_ai_type == "test_generative_ai"
    assert duplicated_ai_field.ai_generative_ai_model == "test_1"
    assert duplicated_ai_field.ai_file_field_id == duplicated_file_field.id
    assert (
        duplicated_ai_field.ai_prompt["formula"]
        == f"concat('test:',get('fields.field_{duplicated_text_field.id}'))"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_duplicate_table_with_ai_field_broken_references(premium_data_fixture):
    session_id = "session-id"
    user = premium_data_fixture.create_user(session_id=session_id)
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="text"
    )
    file_field = premium_data_fixture.create_file_field(
        table=table, order=1, name="file"
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=2,
        name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=file_field,
        ai_prompt=f"concat('test:',get('fields.field_0'))",
    )

    table_handler = TableHandler()
    duplicated_table = table_handler.duplicate_table(user, table)
    duplicated_fields = specific_iterator(
        duplicated_table.field_set.all().order_by("id")
    )
    duplicated_ai_field = duplicated_fields[2]

    assert (
        duplicated_ai_field.ai_prompt["formula"]
        == f"concat('test:',get('fields.field_0'))"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_set_select_options_to_choice_ai_output_type(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()
    premium_data_fixture.create_text_field(table=table, order=1, name="name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "ai",
            "ai_output_type": "choice",
            "ai_generative_ai_type": "test_generative_ai",
            "ai_generative_ai_model": "test_1",
            "ai_prompt": "'Who are you?'",
            "select_options": [
                {"value": "Small", "color": "red"},
                {"value": "Medium", "color": "blue"},
                {"value": "Large", "color": "green"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["ai_output_type"] == "choice"
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"]["formula"] == "'Who are you?'"
    assert len(response_json["select_options"]) == 3


@pytest.mark.django_db
@pytest.mark.field_ai
def test_should_backup(premium_data_fixture, api_client):
    ai_field_type = field_type_registry.get(AIFieldType.type)
    ai_field = premium_data_fixture.create_ai_field()
    file_field = premium_data_fixture.create_file_field(table=ai_field.table)

    assert (
        ai_field_type.should_backup_field_data_for_same_type_update(
            ai_field,
            {
                "ai_generative_ai_type": "test_generative_ai_2",
                "ai_generative_ai_model": "test_model_2",
                "ai_prompt": "'New AI prompt'",
                "ai_output_type": "text",  # same as before
                "ai_temperature": 1,
                "ai_file_field": file_field,
            },
        )
        is False
    )

    assert (
        ai_field_type.should_backup_field_data_for_same_type_update(
            ai_field,
            {
                "ai_generative_ai_type": "test_generative_ai_2",
                "ai_generative_ai_model": "test_model_2",
                "ai_prompt": "'New AI prompt'",
                "ai_output_type": "choice",  # new one
                "ai_temperature": 1,
                "ai_file_field": file_field,
            },
        )
        is True
    )  # Expect to make a backup when output type changes.


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_convert_from_text_output_type_to_choice_output_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_ai_field(
        table=table, order=0, name="ai", ai_output_type="text"
    )

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Option 1"})
    model.objects.create(**{f"field_{field.id}": "Something else"})

    field = FieldHandler().update_field(
        user=user,
        field=field,
        ai_output_type="choice",
        select_options=[
            {"value": "Option 1", "color": "red"},
        ],
    )

    table.refresh_from_db()
    model = table.get_model()
    rows = list(model.objects.all())

    # Converting text ai field to choice field should try to convert the text values to
    # the new choices.
    assert getattr(rows[0], f"field_{field.id}").value == "Option 1"
    assert getattr(rows[1], f"field_{field.id}") is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_convert_from_choice_output_type_to_text_output_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_ai_field(
        table=table, order=0, name="ai", ai_output_type="choice"
    )
    select_option = premium_data_fixture.create_select_option(
        field=field, value="Option 1", color="blue", order=0
    )

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}_id": select_option.id})
    model.objects.create(**{f"field_{field.id}": None})

    field = FieldHandler().update_field(
        user=user,
        field=field,
        ai_output_type="text",
    )

    table.refresh_from_db()
    model = table.get_model()
    rows = list(model.objects.all())

    # Converting choice ai field to text ai field should try to convert the choices to
    # text values.
    assert getattr(rows[0], f"field_{field.id}") == "Option 1"
    assert getattr(rows[1], f"field_{field.id}") is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_convert_from_text_field_to_text_output_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_text_field(table=table, order=0, name="text")

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Test"})

    field = FieldHandler().update_field(
        user=user,
        field=field,
        new_type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'test'",
        ai_output_type="text",
    )

    table.refresh_from_db()
    model = table.get_model()
    rows = list(model.objects.all())

    # Expect the value to be reset because we don't want to keep the existing cell
    # value when converting from any other field.
    assert getattr(rows[0], f"field_{field.id}") is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_convert_from_text_field_to_choice_output_type(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_text_field(table=table, order=0, name="text")

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Test"})

    field = FieldHandler().update_field(
        user=user,
        field=field,
        new_type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'test'",
        ai_output_type="choice",
    )

    table.refresh_from_db()
    model = table.get_model()
    rows = list(model.objects.all())

    # Expect the value to be reset because we don't want to keep the existing cell
    # value when converting from any other field.
    assert getattr(rows[0], f"field_{field.id}") is None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_can_convert_from_text_output_type_to_text_field(
    premium_data_fixture, api_client
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    field = premium_data_fixture.create_ai_field(table=table, order=0, name="ai")

    model = table.get_model()
    model.objects.create(**{f"field_{field.id}": "Test"})

    field = FieldHandler().update_field(
        user=user,
        field=field,
        new_type_name="text",
    )

    table.refresh_from_db()
    model = table.get_model()
    rows = list(model.objects.all())

    # Converting text ai field to text field should keep the values because the text
    # field conversion is automatically used.
    assert getattr(rows[0], f"field_{field.id}") == "Test"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_link_row_field_can_be_sorted_when_linking_an_ai_field(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table_b = premium_data_fixture.create_database_table(user=user)
    primary_b = premium_data_fixture.create_ai_field(
        table=table_b, primary=True, order=1, ai_output_type="choice"
    )

    opt_1 = premium_data_fixture.create_select_option(
        field=primary_b, value="a", color="blue", order=0
    )
    opt_2 = premium_data_fixture.create_select_option(
        field=primary_b, value="b", color="green", order=0
    )

    row_b1, row_b2 = (
        RowHandler()
        .force_create_rows(
            user,
            table_b,
            [
                {primary_b.db_column: opt_1.id},
                {primary_b.db_column: opt_2.id},
            ],
        )
        .created_rows
    )

    table_a, table_b, link_field = premium_data_fixture.create_two_linked_tables(
        user=user, table_b=table_b
    )

    model_a = table_a.get_model()

    RowHandler().force_create_rows(
        user,
        table_a,
        [{link_field.db_column: [row_b.id]} for row_b in [row_b1, row_b2]],
        model=model_a,
    )

    result = list(
        model_a.objects.all()
        .order_by_fields_string(link_field.db_column)
        .values_list("id", flat=True)
    )
    assert result == [row_b1.id, row_b2.id]

    # The sorting should work also for `ai_output_type="text"`

    FieldHandler().update_field(
        user=user,
        field=primary_b,
        ai_output_type="text",
    )

    with local_cache.context():  # After updating the field we want to get the new model
        model_a = table_a.get_model()

        result = list(
            model_a.objects.all()
            .order_by_fields_string(f"-{link_field.db_column}")  # Descending order
            .values_list("id", flat=True)
        )
    assert result == [row_b2.id, row_b1.id]


@pytest.mark.django_db
@pytest.mark.field_ai
def test_formula_field_can_reference_ai_choice_output_without_error(
    premium_data_fixture,
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    ai_choice_field = premium_data_fixture.create_ai_field(
        table=table,
        order=0,
        name="ai_choice",
        ai_output_type="choice",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'pick one'",
    )
    premium_data_fixture.create_select_option(
        field=ai_choice_field, value="Red", color="red", order=0
    )
    premium_data_fixture.create_select_option(
        field=ai_choice_field, value="Blue", color="blue", order=1
    )

    formula_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula_from_ai_choice",
        formula="field('ai_choice')",
    )

    assert formula_field is not None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_can_be_used_in_lookup_expression(premium_data_fixture):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()

    source_table = premium_data_fixture.create_database_table(user=user, name="Source")
    ai_field = premium_data_fixture.create_ai_field(
        table=source_table,
        order=0,
        name="ai_text",
        ai_output_type="text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'Hello World'",
    )

    target_table = premium_data_fixture.create_database_table(user=user, name="Target")
    link_row_field = premium_data_fixture.create_link_row_field(
        table=target_table,
        order=0,
        name="link_to_source",
        link_row_table=source_table,
    )

    formula_field = FieldHandler().create_field(
        user=user,
        table=target_table,
        type_name="formula",
        name="lookup_ai_field",
        formula="lookup('link_to_source', 'ai_text')",
    )

    assert formula_field is not None
    assert formula_field.formula_type == "array"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_type_check_can_filter_by(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(table=table, ai_output_type="text")

    ai_field_type = field_type_registry.get("ai")
    assert ai_field_type.check_can_filter_by(ai_field) is True


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_with_references(premium_data_fixture):
    """
    Test if AI field type handler creates appropriate FieldDependency entries.
    """

    session_id = "session-id"
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(session_id=session_id)
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="text"
    )
    other_text_field = premium_data_fixture.create_text_field(
        table=table, order=0.5, name="other text"
    )
    ai_field = FieldHandler().create_field(
        user=user,
        table=table,
        order=2,
        name="ai_text",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=None,
        ai_prompt=f"concat('test:',get('fields.field_{text_field.id}'), get('fields.field_{other_text_field.id}'))",
    )

    other_ai_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="ai",
        order=3,
        name="other ai field",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=None,
        ai_prompt=f"concat('test:',get('fields.field_{ai_field.id}'))",
    )

    deps = list(FieldDependency.objects.values("dependant_id", "dependency_id"))

    assert len(deps) == 3
    assert deps == unordered(
        [
            {"dependant_id": ai_field.id, "dependency_id": text_field.id},
            {"dependant_id": ai_field.id, "dependency_id": other_text_field.id},
            {"dependant_id": other_ai_field.id, "dependency_id": ai_field.id},
        ]
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_auto_update_user(premium_data_fixture):
    """
    Test if AI field type handler sets the user when auto-update flag is set.
    """

    session_id = "session-id"
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(session_id=session_id)
    database = premium_data_fixture.create_database_application(
        user=user, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="text"
    )
    ai_field: AIField = FieldHandler().create_field(
        user=user,
        table=table,
        order=2,
        name="ai_text",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=None,
        ai_prompt=f"concat('test:',get('fields.field_{text_field.id}'))",
    )

    assert ai_field.ai_auto_update is False
    assert ai_field.ai_auto_update_user_id is None

    FieldHandler().update_field(user=user, field=ai_field, ai_auto_update=True)
    ai_field.refresh_from_db()

    assert ai_field.ai_auto_update is True
    assert ai_field.ai_auto_update_user_id == user.id


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_ai_field_auto_doesnt_update_user_if_set(premium_data_fixture):
    """
    The user should only be set when the auto_update option is enabled.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    other_user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(users=[user, other_user])
    database = premium_data_fixture.create_database_application(
        workspace=workspace, name="Placeholder"
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="text"
    )
    ai_field: AIField = FieldHandler().create_field(
        user=user,
        table=table,
        order=2,
        name="ai_text",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_file_field=None,
        ai_prompt=f"concat('test:',get('fields.field_{text_field.id}'))",
        ai_auto_update=True,
    )

    assert ai_field.ai_auto_update_user_id is user.id

    FieldHandler().update_field(user=other_user, field=ai_field, name="different name")
    ai_field.refresh_from_db()

    assert ai_field.ai_auto_update is True
    assert ai_field.ai_auto_update_user_id == user.id  # not changed
