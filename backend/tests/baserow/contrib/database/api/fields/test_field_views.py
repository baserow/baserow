from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from baserow.contrib.database.fields.models import Field, NumberField, TextField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.contrib.database.views.handler import ViewIndexingHandler
from baserow.contrib.database.views.models import ViewSort
from baserow.core.db import specific_iterator
from baserow.test_utils.helpers import (
    independent_test_db_connection,
    setup_interesting_test_table,
)


@pytest.mark.django_db
def test_list_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(table=table_1, order=1, primary=True)
    field_2 = data_fixture.create_text_field(table=table_1, order=3)
    field_3 = data_fixture.create_number_field(table=table_1, order=2)
    data_fixture.create_boolean_field(table=table_2, order=1)

    token = TokenHandler().create_token(user, table_1.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table_1.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(
        user, wrong_token, False, False, False, True
    )

    # Test access with JWT token
    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 3

    assert response_json[0]["id"] == field_1.id
    assert response_json[0]["type"] == "text"
    assert response_json[0]["primary"]
    assert response_json[0]["text_default"] == field_1.text_default
    assert response_json[0]["read_only"] is False

    assert response_json[1]["id"] == field_3.id
    assert response_json[1]["type"] == "number"
    assert not response_json[1]["primary"]
    assert response_json[1]["number_decimal_places"] == field_3.number_decimal_places
    assert response_json[1]["number_negative"] == field_3.number_negative

    assert response_json[2]["id"] == field_2.id
    assert response_json[2]["type"] == "text"
    assert not response_json[2]["primary"]
    assert response_json[2]["text_default"] == field_2.text_default

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_2.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": 999999}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    # Without any token
    url = reverse("api:database:fields:list", kwargs={"table_id": table_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=table_1.database.workspace)
    table_1.database.workspace.has_template.cache_clear()
    url = reverse("api:database:fields:list", kwargs={"table_id": table_1.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK

    # Test authentication with token
    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": table_1.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_list_read_only_field_types(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_created_on_field(table=table_1, order=1)

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 1
    assert response_json[0]["id"] == field_1.id
    assert response_json[0]["type"] == "created_on"
    assert response_json[0]["read_only"] is True


@pytest.mark.django_db
def test_list_read_only_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table_1 = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(table=table_1, order=1, read_only=True)

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table_1.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {jwt_token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 1
    assert response_json[0]["id"] == field_1.id
    assert response_json[0]["type"] == "text"
    assert response_json[0]["read_only"] is True


@pytest.mark.django_db
def test_create_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, True, True, True)

    # Test operation with JWT token
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "NOT_EXISTING"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["type"][0]["code"] == "invalid_choice"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": 99999}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table_2.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    field_limit = settings.MAX_FIELD_LIMIT
    settings.MAX_FIELD_LIMIT = 0
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAX_FIELD_COUNT_EXCEEDED"
    settings.MAX_FIELD_LIMIT = field_limit

    url = reverse("api:database:fields:list", kwargs={"table_id": table_2.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test no description", "type": "text", "text_default": "default!"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "text"

    text = TextField.objects.filter()[0]
    assert response_json["id"] == text.id
    assert response_json["name"] == "Test no description"
    assert response_json["order"] == text.order
    assert response_json["text_default"] == "default!"
    assert response_json["description"] is None
    text.delete()

    description_txt_a = "This is a description"
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "text",
            "text_default": "default!",
            "description": description_txt_a,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "text"

    text = TextField.objects.filter()[0]
    assert response_json["id"] == text.id
    assert response_json["name"] == text.name
    assert response_json["order"] == text.order
    assert response_json["text_default"] == "default!"
    assert response_json["description"] == description_txt_a
    assert response_json["db_index"] is False

    # Test authentication with token
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    # Even with a token that have all permissions, the call should be rejected
    # for now.
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": text.name, "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS"

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "id", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_RESERVED_BASEROW_FIELD_NAME"

    # Test creating field with too long name
    too_long_field_name = "x" * 256
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": too_long_field_name, "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_get_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    text = data_fixture.create_text_field(table=table)
    number = data_fixture.create_number_field(table=table_2)

    url = reverse("api:database:fields:item", kwargs={"field_id": number.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:fields:item", kwargs={"field_id": 99999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == text.id
    assert response_json["name"] == text.name
    assert response_json["table_id"] == text.table_id
    assert not response_json["text_default"]
    assert response_json["description"] is None
    assert response_json["db_index"] is False

    response = api_client.delete(
        reverse(
            "api:workspaces:item",
            kwargs={"workspace_id": table.database.workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_field(api_client, data_fixture):
    """
    @TODO somehow trigger the CannotChangeFieldType and test if the correct
        ERROR_CANNOT_CHANGE_FIELD_TYPE error is returned.
    """

    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    text = data_fixture.create_text_field(table=table, primary=True)
    text_2 = data_fixture.create_text_field(table=table_2)
    existing_field = data_fixture.create_text_field(table=table, name="existing_field")

    url = reverse("api:database:fields:item", kwargs={"field_id": text_2.id})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:fields:item", kwargs={"field_id": 999999})
    response = api_client.patch(
        url, {"name": "Test 1"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # The primary field is not compatible with a link row field so that should result
    # in an error.
    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url, {"type": "link_row"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE"
    assert (
        response.json()["detail"]
        == "The field type link_row is not compatible with the primary field."
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"UNKNOWN_FIELD": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"name": "Test 1", "text_default": "Something", "description": "a description"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == text.id
    assert response_json["name"] == "Test 1"
    assert response_json["text_default"] == "Something"
    assert response_json["description"] == "a description"

    text.refresh_from_db()
    assert text.name == "Test 1"
    assert text.text_default == "Something"

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {
            "name": "Test 1",
            "type": "text",
            "text_default": "Something",
            "description": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 1"
    assert response_json["type"] == "text"
    assert response_json["description"] is None
    assert response_json["db_index"] is False

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"type": "number", "number_negative": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 1"
    assert response_json["type"] == "number"
    assert response_json["number_decimal_places"] == 0
    assert response_json["number_negative"]

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {
            "number_decimal_places": 2,
            "number_negative": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 1"
    assert response_json["type"] == "number"
    assert response_json["number_decimal_places"] == 2
    assert not response_json["number_negative"]

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"type": "boolean", "name": "Test 2"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "boolean"
    assert "number_decimal_places" not in response_json
    assert "number_negative" not in response_json

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url, {"name": "id"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_RESERVED_BASEROW_FIELD_NAME"

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"name": existing_field.name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS"

    too_long_field_name = "x" * 256
    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.patch(
        url,
        {"name": too_long_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_update_field_immutable_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_type=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_TYPE"


@pytest.mark.django_db
def test_update_field_immutable_type_change_properties(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_type=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"number_decimal_places": 2},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_update_field_immutable_properties(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_properties=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"number_decimal_places": 2},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_PROPERTIES"


@pytest.mark.django_db
def test_update_field_immutable_properties_all_types_change_only_name(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table, *_ = setup_interesting_test_table(data_fixture, user=user)
    table.field_set.all().update(immutable_properties=True)
    all_fields = specific_iterator(table.field_set.all())

    for index, field in enumerate(all_fields):
        field_type = field_type_registry.get_by_model(field)
        if field_type.read_only:
            continue

        url = reverse("api:database:fields:item", kwargs={"field_id": field.id})
        response = api_client.patch(
            url,
            {"name": field.name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_update_field_immutable_properties_change_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_properties=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_PROPERTIES"


@pytest.mark.django_db
def test_update_field_immutable_properties_change_type_and_properties(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_properties=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"type": "text", "text_default": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_PROPERTIES"


@pytest.mark.django_db
def test_update_field_cannot_change_read_only_and_immutable_properties(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {
            "type": "text",
            "read_only": True,
            "immutable_type": True,
            "immutable_properties": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["read_only"] is False
    assert response_json["immutable_type"] is False
    assert response_json["immutable_properties"] is False


@pytest.mark.django_db
@pytest.mark.field_constraints
def test_update_field_immutable_properties_constraints(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        immutable_properties=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"field_constraints": [{"type_name": "unique_with_empty"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_PROPERTIES"


@pytest.mark.django_db
@pytest.mark.field_constraints
def test_update_field_read_only_constraints(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=1,
        read_only=True,
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"field_constraints": [{"type_name": "unique_with_empty"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_IMMUTABLE_FIELD_PROPERTIES"


@pytest.mark.django_db
def test_update_field_number_type_deprecation_error(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, number_decimal_places=1
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {"number_type": "INTEGER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["number_type"][0]["error"] == (
        "The number_type option has been removed and can no longer be provided. "
        "Instead set number_decimal_places to 0 for an integer or 1-5 for a "
        "decimal."
    )


@pytest.mark.django_db
def test_change_field_type_with_active_sort_on_field(api_client, data_fixture):
    import uuid

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name=uuid.uuid4())

    grid = data_fixture.create_grid_view(table=table)

    sort = data_fixture.create_view_sort(view=grid, field=text_field, order="ASC")
    ViewIndexingHandler.update_index(view=grid)

    grid.refresh_from_db()
    assert grid.db_index_name is not None

    # Change the field type from text to number
    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url, {"type": "number"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK

    # Sort is not removed
    assert ViewSort.objects.filter(id=sort.id).exists()

    # Sort index is removed
    grid.refresh_from_db()
    assert grid.db_index_name is None


@pytest.mark.django_db
def test_delete_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user_2)
    text = data_fixture.create_text_field(table=table)
    number = data_fixture.create_number_field(table=table_2)

    url = reverse("api:database:fields:item", kwargs={"field_id": number.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:fields:item", kwargs={"field_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    url = reverse("api:database:fields:item", kwargs={"field_id": text.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200

    assert Field.objects.all().count() == 1
    assert TextField.objects.all().count() == 0
    assert NumberField.objects.all().count() == 1

    table_3 = data_fixture.create_database_table(user=user)
    primary = data_fixture.create_text_field(table=table_3, primary=True)

    url = reverse("api:database:fields:item", kwargs={"field_id": primary.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_CANNOT_DELETE_PRIMARY_FIELD"


@pytest.mark.django_db
def test_unique_row_values(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="11@11.com", password="password", first_name="abcd"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=0, name="Letter")
    grid = data_fixture.create_grid_view(table=table)
    model = grid.table.get_model()

    url = reverse(
        "api:database:fields:unique_row_values", kwargs={"field_id": text_field.id}
    )

    # Check for empty values
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["values"] == []

    # Check that values are sorted by frequency
    values = ["A", "B", "B", "B", "C", "C"]
    for value in values:
        model.objects.create(**{f"field_{text_field.id}": value})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["values"] == ["B", "C", "A"]

    # Check that limit is working
    response = api_client.get(url, {"limit": 1}, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert len(response_json["values"]) == 1

    # Check for non-existent field
    url = reverse("api:database:fields:unique_row_values", kwargs={"field_id": 9999})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_unique_row_values_splitted_by_comma(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="11@11.com", password="password", first_name="abcd"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=0, name="Letter")
    grid = data_fixture.create_grid_view(table=table)
    model = grid.table.get_model()

    # Check that values are sorted by frequency
    values = ["A,B", "C,D,E", "F,E", "G,E", "E", "F", "E,E"]
    for value in values:
        model.objects.create(**{f"field_{text_field.id}": value})

    url = reverse(
        "api:database:fields:unique_row_values", kwargs={"field_id": text_field.id}
    )
    response = api_client.get(
        url, {"split_comma_separated": "true"}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["values"] == ["E", "F", "C", "D", "B", "G", "A"]


@pytest.mark.django_db
def test_unique_row_values_incompatible_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="11@11.com", password="password", first_name="abcd"
    )
    table = data_fixture.create_database_table(user=user)
    # The file field is not compatible.
    file_field = data_fixture.create_file_field(table=table, order=0)

    url = reverse(
        "api:database:fields:unique_row_values", kwargs={"field_id": file_field.id}
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INCOMPATIBLE_FIELD_TYPE_FOR_UNIQUE_VALUES"


@pytest.mark.django_db(transaction=True)
def test_update_field_returns_with_error_if_cant_lock_field_if_locked_for_update(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user, table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_field where id = {text_field.id} FOR UPDATE"
            )
            response = api_client.patch(
                url,
                {"name": "Test 1"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_update_field_returns_with_error_if_cant_lock_field_if_locked_for_key_share(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user, table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_field where id = {text_field.id} FOR KEY SHARE"
            )
            response = api_client.patch(
                url,
                {"name": "Test 1"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_update_field_returns_with_error_if_cant_lock_table_if_locked_for_update(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user, table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR UPDATE"
            )
            response = api_client.patch(
                url,
                {"name": "Test 1"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_update_field_returns_with_error_if_cant_lock_table_if_locked_for_key_share(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user, table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR KEY SHARE"
            )
            response = api_client.patch(
                url,
                {"name": "Test 1"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_create_field_returns_with_error_if_cant_lock_table_if_locked_for_update(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR UPDATE"
            )
            response = api_client.post(
                reverse("api:database:fields:list", kwargs={"table_id": table.id}),
                {"name": "Test 1", "type": "text"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_create_field_returns_with_error_if_cant_lock_table_if_locked_for_key_share(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    with independent_test_db_connection() as conn:
        with conn.cursor() as cursor:
            # nosec
            cursor.execute(
                f"SELECT * FROM database_table where id = {table.id} FOR KEY SHARE"
            )
            response = api_client.post(
                reverse("api:database:fields:list", kwargs={"table_id": table.id}),
                {"name": "Test 1", "type": "text"},
                format="json",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
    response_json = response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response_json["error"] == "ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT"


@pytest.mark.django_db(transaction=True)
def test_async_duplicate_field(api_client, data_fixture):
    user_1, token_1 = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace_1 = data_fixture.create_workspace(user=user_1)
    _, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test2"
    )
    _, token_3 = data_fixture.create_user_and_token(
        email="test_3@test.nl",
        password="password",
        first_name="Test3",
        workspace=workspace_1,
    )

    database = data_fixture.create_database_application(workspace=workspace_1)
    table_1, _, _, _, context = setup_interesting_test_table(
        data_fixture, database=database, user=user_1
    )

    field_set = table_1.field_set.all()
    original_field_count = field_set.count()
    primary_field = field_set.get(primary=True)

    # user cannot duplicate a field if not belonging to the same workspace
    response = api_client.post(
        reverse(
            "api:database:fields:async_duplicate", kwargs={"field_id": primary_field.id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # user cannot duplicate a non-existent field
    response = api_client.post(
        reverse("api:database:fields:async_duplicate", kwargs={"field_id": 99999}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"

    # user can duplicate a field created by other in the same workspace
    response = api_client.post(
        reverse(
            "api:database:fields:async_duplicate", kwargs={"field_id": primary_field.id}
        ),
        {"duplicate_data": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "duplicate_field"

    # check that now the job ended correctly and the field was duplicated
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "duplicate_field"
    assert job["original_field"]["id"] == primary_field.id
    assert job["duplicated_field"]["id"] > primary_field.id
    assert job["duplicated_field"]["name"] == f"{primary_field.name} 2"

    # check that the table is accessible and has one more column
    rows_url = reverse("api:database:rows:list", kwargs={"table_id": table_1.id})
    response = api_client.get(
        f"{rows_url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) > 0
    assert field_set.count() == original_field_count + 1
    for row in response_json["results"]:
        assert row[f"{primary_field.name} 2"] is None

    # user can duplicate a field with data
    response = api_client.post(
        reverse(
            "api:database:fields:async_duplicate", kwargs={"field_id": primary_field.id}
        ),
        {"duplicate_data": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "duplicate_field"

    # check that now the job ended correctly and the field was duplicated
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "duplicate_field"
    assert job["original_field"]["id"] == primary_field.id
    assert job["duplicated_field"]["id"] > primary_field.id
    assert job["duplicated_field"]["name"] == f"{primary_field.name} 3"

    # check that the table is accessible and has one more column
    rows_url = reverse("api:database:rows:list", kwargs={"table_id": table_1.id})
    response = api_client.get(
        f"{rows_url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) > 0
    assert field_set.count() == original_field_count + 2
    for row in response_json["results"]:
        assert row[f"{primary_field.name} 3"] == row[primary_field.name]


@pytest.mark.django_db
def test_change_primary_field_different_table(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)
    table_b = data_fixture.create_database_table(user)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_b.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_FIELD_NOT_IN_TABLE"


@pytest.mark.django_db
def test_change_primary_field_type_not_primary(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_password_field(
        user=user, primary=False, table=table_a
    )

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE"


@pytest.mark.django_db
def test_change_primary_field_field_is_already_primary(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_FIELD_IS_ALREADY_PRIMARY"


@pytest.mark.django_db
def test_change_primary_field_field_no_update_permissions(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_change_primary_field_field_without_primary(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TABLE_HAS_NO_PRIMARY_FIELD"


@pytest.mark.django_db
def test_change_primary_field_field_with_primary(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": field_2.id,
        "table_id": table_a.id,
        "name": field_2.name,
        "order": 0,
        "type": "text",
        "primary": True,
        "read_only": False,
        "description": None,
        "db_index": False,
        "field_constraints": [],
        "related_fields": [
            {
                "id": field_1.id,
                "table_id": table_a.id,
                "name": field_1.name,
                "order": 0,
                "type": "text",
                "primary": False,
                "read_only": False,
                "description": None,
                "db_index": False,
                "field_constraints": [],
                "text_default": "",
                "immutable_properties": False,
                "immutable_type": False,
                "database_id": field_1.table.database.id,
                "workspace_id": field_1.table.database.workspace.id,
            }
        ],
        "text_default": "",
        "immutable_properties": False,
        "immutable_type": False,
        "database_id": table_a.database.id,
        "workspace_id": table_a.database.workspace.id,
    }


@pytest.mark.django_db
def test_change_primary_field_field_and_back(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response = api_client.post(
        reverse(
            "api:database:fields:change_primary_field", kwargs={"table_id": table_a.id}
        ),
        {"new_primary_field_id": field_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    field_1.refresh_from_db()
    field_2.refresh_from_db()
    assert field_1.primary is True
    assert field_2.primary is False


@pytest.mark.django_db
def test_create_field_with_db_index(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Field with index", "type": "text", "db_index": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "text"

    text = TextField.objects.filter()[0]
    assert text.db_index is True
    assert response_json["name"] == "Field with index"
    assert response_json["db_index"] is True


@pytest.mark.django_db
def test_create_field_with_db_index_incompatible_field_type(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Field with index",
            "type": "link_row",
            "db_index": True,
            "link_row_table_id": table_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_DB_INDEX_NOT_SUPPORTED"


@pytest.mark.django_db
def test_update_field_with_db_index(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": field.id})
    response = api_client.patch(
        url,
        {"db_index": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["db_index"] is True

    field.refresh_from_db()
    assert field.db_index is True


@pytest.mark.django_db
def test_update_field_with_db_index_incompatible_field_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)
    field = data_fixture.create_text_field(table=table)

    url = reverse("api:database:fields:item", kwargs={"field_id": field.id})
    response = api_client.patch(
        url,
        {"type": "link_row", "db_index": True, "link_row_table": table_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_DB_INDEX_NOT_SUPPORTED"


@pytest.mark.django_db
def test_update_field_with_db_index_to_incompatible_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)
    field = data_fixture.create_text_field(table=table, db_index=True)

    url = reverse("api:database:fields:item", kwargs={"field_id": field.id})
    response = api_client.patch(
        url,
        {"type": "link_row", "link_row_table": table_2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_DB_INDEX_NOT_SUPPORTED"


@pytest.mark.django_db
def test_password_field_authentication_unauthenticated(api_client, data_fixture):
    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": 0, "row_id": 1, "password": "test"},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_password_field_authentication_field_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": 0, "row_id": 1, "password": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_password_field_authentication_field_disabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(
        user=user, allow_endpoint_authentication=False
    )

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": 1, "password": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_password_field_authentication_row_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(
        user=user, allow_endpoint_authentication=True
    )

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": 1, "password": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_password_field_authentication_wrong_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(
        user=user, allow_endpoint_authentication=True
    )
    model = field.table.get_model()
    row = model.objects.create(**{field.db_column: make_password("password")})

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "wrong_password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_INVALID_PASSWORD_FIELD_PASSWORD"


@pytest.mark.django_db
def test_password_field_authentication_empty_password(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(
        user=user, allow_endpoint_authentication=True
    )
    model = field.table.get_model()
    row = model.objects.create()

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "wrong_password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_INVALID_PASSWORD_FIELD_PASSWORD"


@pytest.mark.django_db
def test_password_field_authentication_success(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(
        user=user, allow_endpoint_authentication=True
    )
    model = field.table.get_model()
    row = model.objects.create(**{field.db_column: make_password("password")})

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["is_correct"] is True


@pytest.mark.django_db
def test_password_field_authentication_no_access_to_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    field = data_fixture.create_password_field(allow_endpoint_authentication=True)
    model = field.table.get_model()
    row = model.objects.create(**{field.db_column: make_password("password")})

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_password_field_authentication_database_token(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    token = TokenHandler().create_token(user, table.database.workspace, "token")
    TokenHandler().update_token_permissions(user, token, True, True, True, True)

    field = data_fixture.create_password_field(
        table=table, allow_endpoint_authentication=True
    )
    model = field.table.get_model()
    row = model.objects.create(**{field.db_column: make_password("password")})

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["is_correct"] is True


@pytest.mark.django_db
def test_password_field_authentication_database_token_no_read_permissions(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    token = TokenHandler().create_token(user, table.database.workspace, "token")
    TokenHandler().update_token_permissions(user, token, True, False, True, True)

    field = data_fixture.create_password_field(
        table=table, allow_endpoint_authentication=True
    )
    model = field.table.get_model()
    row = model.objects.create(**{field.db_column: make_password("password")})

    response = api_client.post(
        reverse("api:database:fields:password_authentication"),
        {"field_id": field.id, "row_id": row.id, "password": "password"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"
