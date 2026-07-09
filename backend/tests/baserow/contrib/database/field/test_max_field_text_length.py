from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["text", "long_text"])
@override_settings(MAX_FIELD_TEXT_LENGTH=10)
def test_text_field_serializer_enforces_length_limit(
    api_client, data_fixture, field_type
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user=user, table=table, type_name=field_type, name="Notes"
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    over_limit = api_client.post(
        url,
        {f"field_{field.id}": "x" * 11},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    over_limit_json = over_limit.json()
    assert over_limit.status_code == HTTP_400_BAD_REQUEST
    assert over_limit_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert over_limit_json["detail"][f"field_{field.id}"][0]["code"] == "max_length"

    at_limit = api_client.post(
        url,
        {f"field_{field.id}": "x" * 10},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert at_limit.status_code == HTTP_200_OK
    assert at_limit.json()[f"field_{field.id}"] == "x" * 10


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["text", "long_text"])
@override_settings(MAX_FIELD_TEXT_LENGTH=10)
def test_text_field_returns_existing_values_over_the_limit(
    api_client, data_fixture, field_type
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user=user, table=table, type_name=field_type, name="Notes"
    )

    # Pre-limit data, inserted directly to bypass the serializer.
    existing = "x" * 25
    row = table.get_model().objects.create(**{field.db_column: existing})

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_200_OK
    assert response.json()[f"field_{field.id}"] == existing


@pytest.mark.django_db
@override_settings(MAX_FIELD_TEXT_LENGTH=15)
def test_url_field_serializer_enforces_length_limit(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user=user, table=table, type_name="url", name="Link"
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    over_limit = api_client.post(
        url,
        {f"field_{field.id}": "http://example.com/too-long-path"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    over_limit_json = over_limit.json()
    assert over_limit.status_code == HTTP_400_BAD_REQUEST
    assert over_limit_json["detail"][f"field_{field.id}"][0]["code"] == "max_length"

    at_limit = api_client.post(
        url,
        {f"field_{field.id}": "http://a.io"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert at_limit.status_code == HTTP_200_OK
    assert at_limit.json()[f"field_{field.id}"] == "http://a.io"
