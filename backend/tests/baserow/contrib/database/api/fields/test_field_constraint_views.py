from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.constants import UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
from baserow.contrib.database.fields.field_constraints import (
    TextTypeUniqueWithEmptyConstraint,
    UniqueWithEmptyConstraint,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


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
            "field_constraints": [
                {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Unique Text Field"
    assert response_json["type"] == "text"
    assert response_json["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
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
            "name": "invalid Constraint Field",
            "type": "text",
            "field_constraints": [{"type_name": "invalid_constraint_name"}],
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
            "field_constraints": [
                {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
            ],
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
            "field_constraints": [
                {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
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


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_constraints
def test_field_constraints_undo_redo(data_fixture):
    """Test that field constraints are properly handled in undo/redo operations."""

    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Test Field",
    )

    assert list(field.field_constraints.values_list("type_name", flat=True)) == []

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        field,
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    field.refresh_from_db()
    assert list(field.field_constraints.values_list("type_name", flat=True)) == [
        TextTypeUniqueWithEmptyConstraint.constraint_name
    ]

    actions = ActionHandler.undo(
        user, [TableActionScopeType.value(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    field.refresh_from_db()
    assert list(field.field_constraints.values_list("type_name", flat=True)) == []

    actions = ActionHandler.redo(
        user, [TableActionScopeType.value(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    field.refresh_from_db()
    assert list(field.field_constraints.values_list("type_name", flat=True)) == [
        TextTypeUniqueWithEmptyConstraint.constraint_name
    ]


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_without_constraints_preserves_existing(api_client, data_fixture):
    """Test that PATCH request without field_constraints preserves existing
    constraints.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Text Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    constraint = text_field.field_constraints.first()
    constraint_id = constraint.id
    assert constraint.type_name == TextTypeUniqueWithEmptyConstraint.constraint_name

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "name": "Updated Text Field",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Updated Text Field"
    assert response_json["field_constraints"] == [
        {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
    ]

    text_field.refresh_from_db()
    assert text_field.field_constraints.count() == 1
    constraint = text_field.field_constraints.get(id=constraint_id)
    assert constraint.type_name == TextTypeUniqueWithEmptyConstraint.constraint_name


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_type_with_incompatible_constraints(api_client, data_fixture):
    """Test updating field type to one that doesn't support existing constraints."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    number_field = handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Number Field",
        field_constraints=[{"type_name": UniqueWithEmptyConstraint.constraint_name}],
    )

    assert number_field.field_constraints.count() == 1
    assert (
        number_field.field_constraints.first().type_name
        == UniqueWithEmptyConstraint.constraint_name
    )

    url = reverse("api:database:fields:item", kwargs={"field_id": number_field.id})
    response = api_client.patch(
        url,
        {
            "type": "boolean",
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
def test_update_field_with_compatible_constraint(api_client, data_fixture):
    """
    Test that PATCH request with compatible constraint preserves
    existing constraints.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Text Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    constraint = text_field.field_constraints.first()
    constraint_id = constraint.id
    assert constraint.type_name == TextTypeUniqueWithEmptyConstraint.constraint_name

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "type": "number",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["type"] == "number"
    assert response_json["field_constraints"] == [
        {"type_name": UniqueWithEmptyConstraint.constraint_name}
    ]
    number_field = NumberField.objects.get(id=text_field.id)

    assert number_field.field_constraints.count() == 1
    constraint = number_field.field_constraints.get(id=constraint_id)
    assert constraint.type_name == UniqueWithEmptyConstraint.constraint_name


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_create_single_select_field_with_default_and_constraint(
    api_client, data_fixture
):
    """
    Test adding field with default value and constraint that does not support
    default value.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "name": "Single Select Field",
            "type": "single_select",
            "single_select_default": -1,
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": -1},
                {"value": "Option 2", "color": "red", "id": -2},
            ],
            "field_constraints": [
                {"type_name": UniqueWithEmptyConstraint.constraint_name}
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert (
        response_json["error"]
        == "ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE"
    )


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_create_text_field_with_default_and_constraint(api_client, data_fixture):
    """
    Test creating a text field with default value and unique with empty constraint
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(table=table, order=0, name="Text Field")
    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Row 1"})
    model.objects.create(**{f"field_{text_field.id}": "Row 2"})

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "name": "Text Field with Default",
            "type": "text",
            "text_default": "Default Value",
            "field_constraints": [{"type_name": UNIQUE_WITH_EMPTY_CONSTRAINT_NAME}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE"
    )


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_add_constraint_to_field_with_default(api_client, data_fixture):
    """Test updating a field to add constraint when it has default value fails."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Text Field", text_default="Default Value"
    )

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Row 1"})
    model.objects.create(**{f"field_{text_field.id}": "Row 2"})

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "field_constraints": [{"type_name": UNIQUE_WITH_EMPTY_CONSTRAINT_NAME}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE"
    )


@pytest.mark.django_db
@pytest.mark.api_fields
@pytest.mark.field_constraints
def test_update_field_remove_default_and_add_constraint_succeeds(
    api_client, data_fixture
):
    """Test updating a field to remove default value and add constraint succeeds."""

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Text Field", text_default="Default Value"
    )

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Row 1"})
    model.objects.create(**{f"field_{text_field.id}": "Row 2"})

    url = reverse("api:database:fields:item", kwargs={"field_id": text_field.id})
    response = api_client.patch(
        url,
        {
            "text_default": "",
            "field_constraints": [{"type_name": UNIQUE_WITH_EMPTY_CONSTRAINT_NAME}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK

    text_field.refresh_from_db()
    assert text_field.text_default == ""
    assert text_field.field_constraints.count() == 1
    assert (
        text_field.field_constraints.first().type_name
        == UNIQUE_WITH_EMPTY_CONSTRAINT_NAME
    )
