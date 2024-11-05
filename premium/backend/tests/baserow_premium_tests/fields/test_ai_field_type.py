from django.shortcuts import reverse

import pytest
from baserow_premium.fields.models import AIField
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
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

    assert ai_field.ai_generative_ai_type == "test_generative_ai"
    assert ai_field.ai_generative_ai_model == "test_1"
    assert ai_field.ai_prompt == "'Who are you?'"
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

    assert ai_field.ai_generative_ai_type == "test_generative_ai"
    assert ai_field.ai_generative_ai_model == "test_1"
    assert ai_field.ai_prompt == "'Who are you?'"


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
    assert response_json["ai_generative_ai_type"] == "test_generative_ai"
    assert response_json["ai_generative_ai_model"] == "test_1"
    assert response_json["ai_prompt"] == "'Who are you?'"
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
    assert response_json["ai_prompt"] == "'Who are you?'"
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
    file_field = premium_data_fixture.create_file_field(
        table=table, order=2, name="file"
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
        duplicated_ai_field.ai_prompt
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

    assert duplicated_ai_field.ai_prompt == f"concat('test:',get('fields.field_0'))"
