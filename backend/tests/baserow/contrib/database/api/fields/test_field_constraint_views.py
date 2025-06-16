from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.field_constraints import (
    TextTypeUniqueWithEmptyConstraint,
)
from baserow.contrib.database.fields.handler import FieldHandler


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_create_field_with_valid_constraint(api_client, data_fixture):
    """Test creating a field with a valid constraint."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "name": "Unique Text Field",
            "type": "text",
            "field_constraints": [{"type": TextTypeUniqueWithEmptyConstraint.type}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Unique Text Field"
    assert response_json["type"] == "text"
    assert response_json["field_constraints"] == [
        {"type": TextTypeUniqueWithEmptyConstraint.type}
    ]


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_create_field_with_invalid_constraint(api_client, data_fixture):
    """Test creating a field with an invalid constraint type."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "name": "Invalid Constraint Field",
            "type": "text",
            "field_constraints": [{"type": "invalid_constraint_type"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_INVALID_FIELD_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_create_field_with_constraint_data_conflict(api_client, data_fixture):
    """Test creating a field with constraint when existing data conflicts."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table, order=0, name="Text Field")

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "duplicate_value"})
    model.objects.create(**{f"field_{text_field.id}": "duplicate_value"})

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "field_constraints": [{"type": TextTypeUniqueWithEmptyConstraint.type}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_with_valid_constraint(api_client, data_fixture):
    """Test updating a field to add a valid constraint."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=0, name="Text Field")

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "field_constraints": [{"type": TextTypeUniqueWithEmptyConstraint.type}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["field_constraints"] == [
        {"type": TextTypeUniqueWithEmptyConstraint.type}
    ]


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_remove_constraint(api_client, data_fixture):
    """Test updating a field to remove constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "field_constraints": [],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["field_constraints"] == []


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_create_row_with_constraint_success(api_client, data_fixture):
    """Test creating a row with a field that has constraints - success case."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "unique_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{text_field.id}"] == "unique_value"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_create_row_with_constraint_violation(api_client, data_fixture):
    """Test creating a row that violates a field constraint."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "duplicate_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "duplicate_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_DATA_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_create_row_with_constraint_empty_value(api_client, data_fixture):
    """Test creating rows with empty values when constraint allows empty."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_batch_create_rows_with_constraint_success(api_client, data_fixture):
    """Test batch creating rows with field constraints - success case."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "items": [
                {f"field_{text_field.id}": "unique_value_1"},
                {f"field_{text_field.id}": "unique_value_2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["items"]) == 2
    assert response_json["items"][0][f"field_{text_field.id}"] == "unique_value_1"
    assert response_json["items"][1][f"field_{text_field.id}"] == "unique_value_2"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_batch_create_rows_with_constraint_violation(api_client, data_fixture):
    """Test batch creating rows that violate field constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "existing_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    batch_url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.post(
        batch_url,
        {
            "items": [
                {f"field_{text_field.id}": "existing_value"},  # Duplicate
                {f"field_{text_field.id}": "new_value"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_DATA_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_update_row_with_constraint_success(api_client, data_fixture):
    """Test updating a row with field constraints - success case."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "initial_value"})

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "updated_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{text_field.id}"] == "updated_value"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_update_row_with_constraint_violation(api_client, data_fixture):
    """Test updating a row that would violate field constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "value_1"})
    row2 = model.objects.create(**{f"field_{text_field.id}": "value_2"})

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row2.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "value_1",  # Duplicate of row1
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_DATA_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_batch_update_rows_with_constraint_success(api_client, data_fixture):
    """Test batch updating rows with field constraints - success case."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "value_1"})
    row2 = model.objects.create(**{f"field_{text_field.id}": "value_2"})

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {
            "items": [
                {
                    "id": row1.id,
                    f"field_{text_field.id}": "updated_value_1",
                },
                {
                    "id": row2.id,
                    f"field_{text_field.id}": "updated_value_2",
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["items"]) == 2
    assert response_json["items"][0][f"field_{text_field.id}"] == "updated_value_1"
    assert response_json["items"][1][f"field_{text_field.id}"] == "updated_value_2"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_batch_update_rows_with_constraint_violation(api_client, data_fixture):
    """Test batch updating rows that would violate field constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "value_1"})
    row2 = model.objects.create(**{f"field_{text_field.id}": "value_2"})
    row3 = model.objects.create(**{f"field_{text_field.id}": "value_3"})

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {
            "items": [
                {
                    "id": row1.id,
                    f"field_{text_field.id}": "updated_value",
                },
                {
                    "id": row2.id,
                    f"field_{text_field.id}": "updated_value",  # Duplicate
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_FIELD_DATA_CONSTRAINT"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_update_row_to_same_value_with_constraint(api_client, data_fixture):
    """Test updating a row to the same value when constraint exists - should succeed."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "existing_value"})

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "existing_value",  # Same value
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[f"field_{text_field.id}"] == "existing_value"


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.field_constraints
def test_create_row_with_constraint_after_removing_constraint(api_client, data_fixture):
    """Test creating rows after removing field constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[{"type": TextTypeUniqueWithEmptyConstraint.type}],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "duplicate_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    field_url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        field_url,
        {
            "field_constraints": [],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        url,
        {
            f"field_{text_field.id}": "duplicate_value",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
