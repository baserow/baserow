from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
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


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_list_jobs_filter_by_type_and_field_id(premium_data_fixture, api_client):
    """Test that generate_ai_values jobs can be filtered by type and field_id."""

    premium_data_fixture.register_fake_generate_ai_type()
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)

    # Create multiple AI fields
    field_1 = premium_data_fixture.create_ai_field(
        table=table, name="ai_1", ai_prompt="'Hello'"
    )
    field_2 = premium_data_fixture.create_ai_field(
        table=table, name="ai_2", ai_prompt="'World'"
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}]).created_rows

    # Create jobs for field_1
    response_1 = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field_1.id},
        ),
        {"row_ids": [rows[0].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response_1.status_code == HTTP_202_ACCEPTED
    job_1_id = response_1.json()["id"]

    # Create jobs for field_2
    response_2 = api_client.post(
        reverse(
            "api:premium:fields:async_generate_ai_field_values",
            kwargs={"field_id": field_2.id},
        ),
        {"row_ids": [rows[1].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response_2.status_code == HTTP_202_ACCEPTED
    job_2_id = response_2.json()["id"]

    # Test filtering by type only
    jobs_url = reverse("api:jobs:list")
    response = api_client.get(
        f"{jobs_url}?type=generate_ai_values",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_data = response.json()
    job_ids = [job["id"] for job in response_data["jobs"]]
    assert job_1_id in job_ids
    assert job_2_id in job_ids
    # All returned jobs should be of type generate_ai_values
    assert all(job["type"] == "generate_ai_values" for job in response_data["jobs"])

    # Test filtering by type and field_id for field_1
    response = api_client.get(
        f"{jobs_url}?type=generate_ai_values&generate_ai_values_field_id={field_1.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_data = response.json()
    assert len(response_data["jobs"]) == 1
    assert response_data["jobs"][0]["id"] == job_1_id
    assert response_data["jobs"][0]["type"] == "generate_ai_values"
    assert response_data["jobs"][0]["field_id"] == field_1.id

    # Test filtering by type and field_id for field_2
    response = api_client.get(
        f"{jobs_url}?type=generate_ai_values&generate_ai_values_field_id={field_2.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_data = response.json()
    assert len(response_data["jobs"]) == 1
    assert response_data["jobs"][0]["id"] == job_2_id
    assert response_data["jobs"][0]["type"] == "generate_ai_values"
    assert response_data["jobs"][0]["field_id"] == field_2.id
