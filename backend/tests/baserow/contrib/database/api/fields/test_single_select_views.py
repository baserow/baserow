from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.models import SelectOption


@pytest.mark.django_db
@pytest.mark.field_single_select
@pytest.mark.api_rows
def test_batch_create_rows_single_select_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 2",
        color="yellow",
    )
    single_select_field.select_options.set([select_option_1, select_option_2])
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{single_select_field.id}": select_option_2.id,
            },
            {
                f"field_{single_select_field.id}": select_option_1.id,
            },
            {
                f"field_{single_select_field.id}": None,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"field_{single_select_field.id}": {
                    "id": select_option_2.id,
                    "color": "yellow",
                    "value": "Option 2",
                },
                "order": "1.00000000000000000000",
            },
            {
                f"id": 2,
                f"field_{single_select_field.id}": {
                    "id": select_option_1.id,
                    "color": "blue",
                    "value": "Option 1",
                },
                "order": "2.00000000000000000000",
            },
            {
                f"id": 3,
                f"field_{single_select_field.id}": None,
                "order": "3.00000000000000000000",
            },
        ]
    }

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body


@pytest.mark.django_db
@pytest.mark.field_single_select
@pytest.mark.api_rows
def test_batch_update_rows_single_select_field_wrong_option(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_field.select_options.set([select_option_1])
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{single_select_field.id}": 787,
            },
            {
                f"id": row_2.id,
                f"field_{single_select_field.id}": select_option_1.id,
            },
        ]
    }

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response.json()["detail"]
        == "The provided select option value '787' is not a valid select option."
    )


@pytest.mark.django_db
@pytest.mark.field_single_select
def test_cannot_pass_internal_force_create_option(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    single_select_field = data_fixture.create_single_select_field(table=table)
    url = reverse(
        "api:database:fields:item", kwargs={"field_id": single_select_field.id}
    )
    response = api_client.patch(
        url,
        {
            "select_options": [
                {
                    "value": "Option 1",
                    "color": "blue",
                    "internal_only_force_create_with_pk": 9999,
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    created_option = SelectOption.objects.get()
    assert created_option.id != 9999
    assert created_option.value == "Option 1"
    assert created_option.color == "blue"


@pytest.mark.django_db
def test_single_select_field_with_default_value(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # New field with new option as default
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Single",
            "type": "single_select",
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": -1},
                {"value": "Option 2", "color": "red", "id": -2},
            ],
            "single_select_default": -1,  # Set first option as default
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    field_data = response.json()
    select_option_1_id = field_data["select_options"][0]["id"]
    select_option_2_id = field_data["select_options"][1]["id"]

    assert len(field_data["select_options"]) == 2
    assert field_data["single_select_default"] == select_option_1_id

    # Update the field to use existing option as default
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {"single_select_default": select_option_2_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    updated_field = response.json()
    assert updated_field["single_select_default"] == select_option_2_id

    # Add new option and but don't set it as default
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
                {"value": "Option 3", "color": "green", "id": -1},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    final_field = response.json()
    select_option_3_id = final_field["select_options"][2]["id"]
    assert final_field["single_select_default"] == select_option_2_id

    # Add new option and set it as default in the same request
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
                {"value": "Option 3", "color": "green", "id": select_option_3_id},
                {"value": "Option 4", "color": "yellow", "id": -1},
            ],
            "single_select_default": -1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    final_field = response.json()
    select_option_4_id = final_field["select_options"][3]["id"]
    assert len(final_field["select_options"]) == 4
    assert final_field["single_select_default"] == select_option_4_id

    # Delete option that is set as default, but don't send default value and verify
    # default is set to None
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
                {"value": "Option 3", "color": "green", "id": select_option_3_id},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    deleted_field = response.json()
    assert len(deleted_field["select_options"]) == 3
    assert deleted_field["single_select_default"] is None

    # Set default to existing option
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {"single_select_default": select_option_3_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    # Delete delete option that is set as default but send also default value and
    # verify error
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
            ],
            "single_select_default": select_option_3_id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    deleted_field = response.json()
    assert deleted_field["error"] == "ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD"
    assert (
        deleted_field["detail"]
        == f"Select option {select_option_3_id} does not belong to field {field_data['id']}"
    )

    # Set default to existing option
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {"single_select_default": select_option_2_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    # Delete delete option that is set as default
    # but also set default to some other option
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
            ],
            "single_select_default": select_option_1_id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    final_field = response.json()
    assert final_field["single_select_default"] == select_option_1_id

    # Set default to None, don't change any options
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
            ],
            "single_select_default": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    final_field = response.json()
    assert final_field["single_select_default"] is None


@pytest.mark.django_db
def test_add_single_select_field_with_default_sets_existing_rows(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()

    for _ in range(3):
        model.objects.create()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Single",
            "type": "single_select",
            "select_options": [
                {"value": "A", "color": "blue", "id": -1},
                {"value": "B", "color": "red", "id": -2},
            ],
            "single_select_default": -1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    field_data = response.json()
    field_id = field_data["id"]
    select_option_id = field_data["select_options"][0]["id"]
    assert field_data["single_select_default"] == select_option_id

    model = table.get_model()
    for row in model.objects.all():
        value = getattr(row, f"field_{field_id}")
        assert value is not None
        assert value.id == select_option_id
