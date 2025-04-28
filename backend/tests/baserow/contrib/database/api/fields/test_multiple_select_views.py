from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.test_utils.helpers import is_dict_subset


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_create_rows_multiple_select_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 3",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1, select_option_2])
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{multiple_select_field.id}": [select_option_3.id],
            },
            {
                f"field_{multiple_select_field.id}": [
                    select_option_3.id,
                    select_option_2.id,
                ],
            },
            {
                f"field_{multiple_select_field.id}": [],
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"}
                ],
                "order": "1.00000000000000000000",
            },
            {
                f"id": 2,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"},
                    {"id": select_option_2.id, "color": "blue", "value": "Option 2"},
                ],
                "order": "2.00000000000000000000",
            },
            {
                f"id": 3,
                f"field_{multiple_select_field.id}": [],
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
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{multiple_select_field.id}").count() == 1
    assert getattr(rows[1], f"field_{multiple_select_field.id}").count() == 2
    assert getattr(rows[2], f"field_{multiple_select_field.id}").count() == 0


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_create_rows_multiple_select_field_with_string_as_value(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 3",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1, select_option_2])
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{multiple_select_field.id}": "Option 3",
            },
            {
                f"field_{multiple_select_field.id}": "Option 3,Option 2",
            },
            {
                f"field_{multiple_select_field.id}": "",
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"}
                ],
                "order": "1.00000000000000000000",
            },
            {
                f"id": 2,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"},
                    {"id": select_option_2.id, "color": "blue", "value": "Option 2"},
                ],
                "order": "2.00000000000000000000",
            },
            {
                f"id": 3,
                f"field_{multiple_select_field.id}": [],
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
    rows = model.objects.all()
    assert getattr(rows[0], f"field_{multiple_select_field.id}").count() == 1
    assert getattr(rows[1], f"field_{multiple_select_field.id}").count() == 2
    assert getattr(rows[2], f"field_{multiple_select_field.id}").count() == 0


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_create_rows_multiple_select_field_with_invalid_string_as_value(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1, select_option_2])
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{multiple_select_field.id}": "Option 4,Option 2",
            },
        ]
    }

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_REQUEST_BODY_VALIDATION",
        "detail": "The provided select option value 'Option 4' is not a valid select option.",
    }


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_update_rows_multiple_select_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 3",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1, select_option_2])
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    row_3 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{multiple_select_field.id}": [select_option_3.id],
            },
            {
                f"id": row_2.id,
                f"field_{multiple_select_field.id}": [
                    select_option_3.id,
                    select_option_2.id,
                ],
            },
            {
                f"id": row_3.id,
                f"field_{multiple_select_field.id}": [],
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"}
                ],
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"field_{multiple_select_field.id}": [
                    {"id": select_option_3.id, "color": "blue", "value": "Option 3"},
                    {"id": select_option_2.id, "color": "blue", "value": "Option 2"},
                ],
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_3.id,
                f"field_{multiple_select_field.id}": [],
                "order": "1.00000000000000000000",
            },
        ]
    }

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body
    assert getattr(row_1, f"field_{multiple_select_field.id}").count() == 1
    assert getattr(row_2, f"field_{multiple_select_field.id}").count() == 2
    assert getattr(row_3, f"field_{multiple_select_field.id}").count() == 0


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_update_rows_multiple_select_field_wrong_option(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1])
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{multiple_select_field.id}": [787],
            },
            {
                f"id": row_2.id,
                f"field_{multiple_select_field.id}": [789, select_option_1.id],
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
        == "The provided select option values [787, 789] are not valid select options."
    )


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_update_rows_multiple_select_field_null_as_id(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1])
    model = table.get_model()
    row_1 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{multiple_select_field.id}": [None],
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
        == "The provided value '[None]' is not a valid integer or string."
    )


@pytest.mark.django_db
@pytest.mark.field_multiple_select
@pytest.mark.api_rows
def test_batch_update_rows_multiple_select_field_maintain_relationships(
    api_client, data_fixture
):
    """
    Since we are deleting and recreating m2m relationships we want to be sure
    that already existing relationships are preserved
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    # first select field
    select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_1, select_option_2])
    multiple_select_field_b = data_fixture.create_multiple_select_field(table=table)
    # second select field
    select_option_b_1 = SelectOption.objects.create(
        field=multiple_select_field_b,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_b_2 = SelectOption.objects.create(
        field=multiple_select_field_b,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set([select_option_b_1, select_option_b_2])
    model = table.get_model()
    # store some data beforehand
    row_1 = model.objects.create()
    getattr(row_1, f"field_{multiple_select_field.id}").set([select_option_1.id])
    getattr(row_1, f"field_{multiple_select_field_b.id}").set([select_option_b_2.id])
    row_1.save()
    row_2 = model.objects.create()
    getattr(row_2, f"field_{multiple_select_field.id}").set(
        [select_option_1.id, select_option_2.id]
    )
    getattr(row_2, f"field_{multiple_select_field_b.id}").set(
        [select_option_1.id, select_option_2.id]
    )
    row_2.save()

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_2.id,
                f"field_{multiple_select_field.id}": [],
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_2.id,
                f"field_{multiple_select_field.id}": [],
            },
        ]
    }

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(expected_response_body, response.json())
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{multiple_select_field.id}").count() == 1
    assert getattr(row_2, f"field_{multiple_select_field.id}").count() == 0
    assert getattr(row_1, f"field_{multiple_select_field_b.id}").count() == 1
    assert getattr(row_2, f"field_{multiple_select_field_b.id}").count() == 2


@pytest.mark.django_db
@pytest.mark.field_formula
@pytest.mark.api_rows
def test_batch_update_rows_when_single_select_formula_in_an_error_state(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(user, table=table)
    option_field = data_fixture.create_single_select_field(user, table=table)
    option_a = data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )

    formula_field = FieldHandler().create_field(
        user, table, "formula", formula=f"field('{option_field.name}')", name="formula"
    )

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    # Now break the formula field by deleting it's option field. Under the hood it is
    # still represented by a JSONB column in the database even though it is broken.

    FieldHandler().delete_field(user, option_field)
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {f"id": row_1.id, f"field_{text_field.id}": "a"},
            {f"id": row_2.id, f"field_{text_field.id}": "b"},
        ]
    }

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_multiple_select_field_with_default_value(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # New field with new option as default
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Multiple",
            "type": "multiple_select",
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": -1},
                {"value": "Option 2", "color": "red", "id": -2},
            ],
            "multiple_select_default": [-1],  # Set first option as default
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK

    field_data = response.json()

    select_option_1_id = field_data["select_options"][0]["id"]
    select_option_2_id = field_data["select_options"][1]["id"]
    assert len(field_data["select_options"]) == 2
    assert field_data["multiple_select_default"] == [select_option_1_id]

    # Update the field to use existing option as default
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "multiple_select_default": [
                select_option_1_id,
                select_option_2_id,
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    updated_field = response.json()
    assert updated_field["multiple_select_default"] == [
        select_option_1_id,
        select_option_2_id,
    ]

    # Add new option but do not set it as default
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
                {"value": "Option 3", "color": "green", "id": -1},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    updated_field = response.json()
    select_option_3_id = updated_field["select_options"][2]["id"]
    assert updated_field["multiple_select_default"] == [
        select_option_1_id,
        select_option_2_id,
    ]

    # Add new option and set it as default in the same update
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
                {"value": "Option 3", "color": "green", "id": select_option_3_id},
                {"value": "Option 4", "color": "yellow", "id": -1},
            ],
            "multiple_select_default": [
                select_option_1_id,
                select_option_2_id,
                select_option_3_id,
                -1,
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    final_field = response.json()
    select_option_4_id = final_field["select_options"][3]["id"]
    assert len(final_field["select_options"]) == 4
    assert final_field["multiple_select_default"] == [
        select_option_1_id,
        select_option_2_id,
        select_option_3_id,
        select_option_4_id,
    ]

    # Update the field to use non-existing option as default
    invalid_option_id = 50000000
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {"multiple_select_default": [select_option_1_id, invalid_option_id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    updated_field = response.json()
    assert updated_field["error"] == "ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD"
    assert (
        updated_field["detail"]
        == f"Select option {invalid_option_id} does not belong to field {field_data['id']}"
    )

    # Delete option that is set in default, but don't send it in the request
    # and verify default is updated
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
                {"value": "Option 2", "color": "red", "id": select_option_2_id},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    deleted_field = response.json()
    assert len(deleted_field["select_options"]) == 2
    assert deleted_field["multiple_select_default"] == [
        select_option_1_id,
        select_option_2_id,
    ]

    # Delete option that is set in default, but also set it as default - expect error
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
            ],
            "multiple_select_default": [
                select_option_1_id,
                select_option_2_id,
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    deleted_field = response.json()
    assert deleted_field["error"] == "ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD"
    assert (
        deleted_field["detail"]
        == f"Select option {select_option_2_id} does not belong to field {field_data['id']}"
    )

    # Delete option that is set in default but also update properly default
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "select_options": [
                {"value": "Option 1", "color": "blue", "id": select_option_1_id},
            ],
            "multiple_select_default": [
                select_option_1_id,
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    deleted_field = response.json()
    assert len(deleted_field["select_options"]) == 1
    assert deleted_field["multiple_select_default"] == [
        select_option_1_id,
    ]

    # Clear default without updating options - default is updated
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_data["id"]}),
        {
            "multiple_select_default": [],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    deleted_field = response.json()
    assert len(deleted_field["select_options"]) == 1
    assert deleted_field["multiple_select_default"] == []


@pytest.mark.django_db
def test_add_multiple_select_field_with_default_sets_existing_rows(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()

    for _ in range(3):
        model.objects.create()

    # Add a new multiple select field with new options and a default value
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Multi",
            "type": "multiple_select",
            "select_options": [
                {"value": "A", "color": "blue", "id": -1},
                {"value": "B", "color": "red", "id": -2},
            ],
            "multiple_select_default": [-1, -2],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    field_data = response.json()
    field_id = field_data["id"]
    select_option_ids = [opt["id"] for opt in field_data["select_options"]]
    assert field_data["multiple_select_default"] == select_option_ids

    model = table.get_model()
    for row in model.objects.all():
        value = getattr(row, f"field_{field_id}").all()
        value_ids = sorted([v.id for v in value])
        assert value_ids == sorted(select_option_ids)
