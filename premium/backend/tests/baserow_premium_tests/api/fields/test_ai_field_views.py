from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_without_license(premium_data_fixture, api_client):
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
    field = premium_data_fixture.create_ai_field(table=table, name="ai")

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_field_does_not_exist(
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
    field = premium_data_fixture.create_ai_field(table=table, name="ai")

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": 0},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_FIELD_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_row_does_not_exist(
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
    field = premium_data_fixture.create_ai_field(table=table, name="ai")

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [0]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_user_not_in_workspace(
    premium_data_fixture, api_client
):
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
    field = premium_data_fixture.create_ai_field(table=table, name="ai")

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_generative_ai_does_not_exist(
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
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_generative_ai_type="does_not_exist"
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GENERATIVE_AI_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_generative_ai_model_does_not_belong_to_type(
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
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_generative_ai_model="does_not_exist"
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {},
            ],
        )
        .created_rows
    )

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE"


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_value_view_generative_ai(premium_data_fixture, api_client):
    """Test that the API endpoint creates a job to generate AI field values."""

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
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt="'Hello'"
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows

    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_202_ACCEPTED

    # Verify the response contains job data
    response_json = response.json()
    assert "id" in response_json  # Job ID
    assert response_json["type"] == "generate_ai_values"
    assert response_json["state"] in [
        "pending",
        "finished",
    ]  # Might complete immediately in tests


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_batch_generate_ai_field_value_limit(api_client, premium_data_fixture):
    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt="'Hello'"
    )
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{}] * (settings.BATCH_ROWS_SIZE_LIMIT + 1),
        )
        .created_rows
    )

    row_ids = [row.id for row in rows]

    # BATCH_ROWS_SIZE_LIMIT rows are allowed
    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": row_ids[: settings.BATCH_ROWS_SIZE_LIMIT]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_202_ACCEPTED

    # BATCH_ROWS_SIZE_LIMIT + 1 rows are not allowed
    response = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field.id},
        ),
        {"row_ids": row_ids},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == {
        "row_ids": [
            {
                "code": "max_length",
                "error": f"Ensure this field has no more than"
                f" {settings.BATCH_ROWS_SIZE_LIMIT} elements.",
            },
        ],
    }
