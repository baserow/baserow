from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.django_db
def test_altering_value_of_referenced_field(data_fixture, api_client):
    expected = "2"
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    number_field_id = response.json()["id"]

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_id = response.json()["id"]

    # Create a row
    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{number_field_id}": 1},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    row_id = response.json()["id"]
    assert response.status_code == 200, response.json()

    # Assert the formula has calculated correctly
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == expected

    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row_id},
        ),
        {f"field_{number_field_id}": 2},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert response.json()[f"field_{formula_field_id}"] == "3"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "3"


@pytest.mark.django_db
def test_changing_type_of_reference_field_to_invalid_one_for_formula(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        {"type": "boolean"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["related_fields"][0]["id"] == formula_field_id
    assert response_json["related_fields"][0]["formula_type"] == "invalid"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] is None

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "argument number 2" in response_json[1]["error"]


@pytest.mark.django_db
def test_changing_name_of_referenced_field_by_formula(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        {"name": "new_name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"


@pytest.mark.django_db
def test_trashing_child_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["related_fields"]) == 1
    assert response_json["related_fields"][0]["id"] == formula_field_id
    assert (
        "references the deleted or unknown field number"
        in response_json["related_fields"][0]["error"]
    )

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "references the deleted or unknown field number" in response_json[0]["error"]


@pytest.mark.django_db
def test_trashing_restoring_child_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "references the deleted or unknown field number" in response_json[0]["error"]
    assert response_json[0]["formula"] == "field('number')+1"

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": "field",
            "trash_item_id": fields[0].id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json[1]["error"] is None
    assert response_json[1]["formula"] == f"field('{fields[0].name}')+1"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"


@pytest.mark.django_db
def test_trashing_renaming_child_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number"), ("number2", "number")], rows=[[1, 2]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "references the deleted or unknown field number" in response_json[1]["error"]
    assert response_json[1]["formula"] == "field('number')+1"

    # We rename the other field to fit into the formula slot
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[1].id}),
        {"name": "number"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json[1]["error"] is None
    assert response_json[1]["formula"] == f"field('number')+1"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "3"


@pytest.mark.django_db
def test_trashing_creating_child_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert "references the deleted or unknown field number" in response_json[0]["error"]
    assert response_json[0]["formula"] == "field('number')+1"

    # We create the another field to fit into the formula slot
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:fields:item", kwargs={"field_id": formula_field_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json["error"] is None
    assert response_json["formula"] == f"field('number')+1"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1"


@pytest.mark.django_db
def test_cant_make_self_reference(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('Formula')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_SELF_REFERENCE"


@pytest.mark.django_db
def test_cant_make_circular_reference(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    first_formula_field_id = response.json()["id"]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('Formula')"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.patch(
        reverse(
            "api:database:fields:item", kwargs={"field_id": first_formula_field_id}
        ),
        {"name": "Formula", "type": "formula", "formula": "field('Formula2')"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_CIRCULAR_REFERENCE"


@pytest.mark.django_db
def test_changing_type_of_reference_field_to_valid_one_for_formula(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("text", "text")], rows=[["1"], ["not a number"]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "concat(field('text'),'test')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1test"
    assert (
        response_json["results"][1][f"field_{formula_field_id}"] == "not a numbertest"
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        {"type": "number"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1test"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "test"


@pytest.mark.django_db
def test_can_set_number_of_decimal_places(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[["1"], ["2"]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "1/4",
            "number_type": "DECIMAL",
            "number_decimal_places": 5,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "0.25000"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "0.25000"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": formula_field_id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "1/4",
            "number_type": "DECIMAL",
            "number_decimal_places": 2,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "0.25"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "0.25"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": formula_field_id}),
        {
            "name": "Formula",
            "type": "text",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "0.25"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "0.25"


@pytest.mark.django_db
def test_altering_type_of_underlying_causes_type_update(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("text", "text")], rows=[["1"], [None]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "field('text')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{formula_field_id}"] is None

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        {
            "name": "text",
            "type": "number",
            "number_decimal_places": 2,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1.00"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "0.00"


@pytest.mark.django_db
def test_can_compare_date_and_text(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_date_field(
        table=table,
        date_include_time=True,
        date_format="US",
        name="Date",
    )
    data_fixture.create_text_field(table=table, name="Text")
    model = table.get_model(attribute_names=True)
    model.objects.create(date="2020-01-01 12:00", text="01/01/2020 12:00")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "field('Date')=field('Text')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"]


@pytest.mark.django_db
def test_trashing_row_changing_formula_restoring_row(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1], [2]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.delete(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "3"

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": formula_field_id}),
        {
            "formula": "'a'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    model = table.get_model()
    formula_values = model.objects_and_trash.values_list(
        f"field_{formula_field_id}", flat=True
    )
    assert list(formula_values) == ["a", "a"]

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": "row",
            "trash_item_id": rows[0].id,
            "parent_trash_item_id": table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "a"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "a"


@pytest.mark.django_db
def test_trashing_formula_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("number", "number")], rows=[[1]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == "2"

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": formula_field_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert f"field_{formula_field_id}" not in response_json["results"][0]


@pytest.mark.django_db
def test_cant_type_an_invalid_formula_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_name = response.json()["name"]

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {f"formula": "1+'a'", "name": formula_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 400, response_json
    assert response_json["error"] == "ERROR_WITH_FORMULA"


@pytest.mark.django_db
def test_can_type_a_valid_formula_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_name = response.json()["name"]

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {"formula": "1+1", "name": formula_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200, response_json
    assert response_json == {
        "date_format": None,
        "date_include_time": None,
        "date_time_format": None,
        "date_show_tzinfo": None,
        "date_force_timezone": None,
        "duration_format": None,
        "error": None,
        "formula": "1+1",
        "formula_type": "number",
        "nullable": False,
        "array_formula_type": None,
        "number_decimal_places": 0,
        "number_prefix": "",
        "number_separator": "",
        "number_suffix": "",
    }


@pytest.mark.django_db
def test_type_endpoint_returns_error_for_bad_syntax(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_name = response.json()["name"]

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {f"formula": "bad syntax", "name": formula_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_WITH_FORMULA"


@pytest.mark.django_db
def test_type_endpoint_returns_error_for_missing_parameters(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_type_endpoint_returns_error_for_missing_table(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    response = api_client.post(
        reverse("api:database:formula:type_formula", kwargs={"table_id": 9999}),
        {f"formula": "bad syntax", "name": "field_name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_type_endpoint_returns_error_for_self_reference(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "formula", "type": "formula", "formula": "'a'"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_name = response.json()["name"]

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {f"formula": "field('formula')", "name": formula_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_SELF_REFERENCE"


@pytest.mark.django_db
def test_type_endpoint_returns_error_if_not_permissioned_for_table(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "number", "type": "number", "number_decimal_places": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()

    # Create a formula field referencing the normal number field
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula2", "type": "formula", "formula": "field('number')+1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    formula_field_name = response.json()["name"]

    response = api_client.post(
        reverse(
            "api:database:formula:type_formula",
            kwargs={"table_id": table.id},
        ),
        {f"formula": "1+1", "name": formula_field_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_altering_type_of_underlying_causes_type_update_nested(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("text", "text")], rows=[["1"], [None]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "field('text')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula2",
            "type": "formula",
            "formula": "field('Formula')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    nested_formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{formula_field_id}"] is None
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] is None

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        {
            "name": "text",
            "type": "number",
            "number_decimal_places": 2,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1.00"
    assert response_json["results"][1][f"field_{formula_field_id}"] == "0.00"
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] == "1.00"
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] == "0.00"


@pytest.mark.django_db
def test_deleting_underlying_causes_type_update_nested(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("text", "text")], rows=[["1"], [None]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "field('text')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula2",
            "type": "formula",
            "formula": "field('Formula')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    nested_formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{formula_field_id}"] is None
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] is None

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["related_fields"]) == 2
    assert (
        response_json["related_fields"][0]["error"]
        == "references the deleted or unknown field text"
    )
    assert (
        response_json["related_fields"][1]["error"] == "references the deleted or "
        "unknown field text"
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] is None
    assert response_json["results"][1][f"field_{formula_field_id}"] is None
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] is None
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] is None


@pytest.mark.django_db
def test_deleting_underlying_causes_type_update_nested_after_update(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table, fields, rows = data_fixture.build_table(
        columns=[("text", "text")], rows=[["1"], [None]], user=user
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula",
            "type": "formula",
            "formula": "field('text')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Formula2",
            "type": "formula",
            "formula": "1",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    nested_formula_field_id = response_json["id"]

    response = api_client.patch(
        reverse(
            "api:database:fields:item", kwargs={"field_id": nested_formula_field_id}
        ),
        {
            "formula": "field('Formula')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{formula_field_id}"] is None
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] == "1"
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] is None

    response = api_client.delete(
        reverse("api:database:fields:item", kwargs={"field_id": fields[0].id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["related_fields"]) == 2
    assert (
        response_json["related_fields"][0]["error"]
        == "references the deleted or unknown field text"
    )
    assert (
        response_json["related_fields"][1]["error"] == "references the deleted or "
        "unknown field text"
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 2
    assert response_json["results"][0][f"field_{formula_field_id}"] is None
    assert response_json["results"][1][f"field_{formula_field_id}"] is None
    assert response_json["results"][0][f"field_{nested_formula_field_id}"] is None
    assert response_json["results"][1][f"field_{nested_formula_field_id}"] is None


@pytest.mark.django_db
def test_referencing_single_select(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    option_field = data_fixture.create_single_select_field(table=table, name="option")
    option_a = data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    data_fixture.create_select_option(field=option_field, value="B", color="red")
    table.get_model(attribute_names=True).objects.create(option=option_a)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Formula", "type": "formula", "formula": "field('option')"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    formula_field_id = response_json["id"]

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0][f"field_{formula_field_id}"] == {
        "color": "blue",
        "id": option_a.id,
        "value": "A",
    }

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response_json
    response_json = response.json()
