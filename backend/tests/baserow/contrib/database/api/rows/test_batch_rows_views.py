from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.shortcuts import reverse
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.test_utils.helpers import AnyStr, is_dict_subset
from tests.baserow.contrib.database.utils import get_deadlock_error

# Create


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_batch_create_rows_invalid_token(api_client, data_fixture, token_header):
    table = data_fixture.create_database_table()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_token_no_create_permission(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    no_create_perm_token = TokenHandler().create_token(
        user, table.database.workspace, "no permissions"
    )
    TokenHandler().update_token_permissions(
        user, no_create_perm_token, False, True, True, True
    )
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Token {no_create_perm_token.key}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_user_not_in_workspace(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table()
    request_body = {
        "items": [
            {
                f"field_11": "green",
            },
        ]
    }
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_invalid_table_id(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    url = reverse("api:database:rows:batch", kwargs={"table_id": 14343})

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_no_rows_provided(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": []}
    expected_error_detail = {
        "items": [
            {
                "code": "min_length",
                "error": "Ensure this field has at least 1 elements.",
            },
        ],
    }

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == expected_error_detail


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_batch_size_limit(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    num_rows = settings.BATCH_ROWS_SIZE_LIMIT + 1
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{f"field_{number_field.id}": i} for i in range(num_rows)]}
    expected_error_detail = {
        "items": [
            {
                "code": "max_length",
                "error": f"Ensure this field has no more than"
                f" {settings.BATCH_ROWS_SIZE_LIMIT} elements.",
            },
        ],
    }

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == expected_error_detail


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_field_validation(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
            },
            {
                f"field_{number_field.id}": -200,
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
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response.json()["detail"]["items"]["1"][f"field_{number_field.id}"][0]["code"]
        == "min_value"
    )


@pytest.mark.django_db
def test_cannot_batch_create_rows_with_data_sync(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_ical_data_sync(table=table)

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{}]}
    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_CREATE_ROWS_IN_TABLE"


@pytest.mark.parametrize("include_metadata", [True, False])
@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows(api_client, data_fixture, include_metadata):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    number_field_2 = data_fixture.create_number_field(
        table=table, order=2, name="Price", number_default=1000
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=3, name="For sale"
    )
    boolean_field_2 = data_fixture.create_boolean_field(
        table=table, order=4, name="Available", boolean_default=True
    )
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": 120,
                f"field_{number_field_2.id}": 2000,
                f"field_{boolean_field.id}": True,
                f"field_{boolean_field_2.id}": False,
            },
            {
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": 240,
                f"field_{boolean_field.id}": False,
                # Not providing number_field_2 should use the default 1000 value
                # Not providing boolean_field_2 should use the default True value
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                "id": 1,
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": "120",
                f"field_{number_field_2.id}": "2000",
                f"field_{boolean_field.id}": True,
                f"field_{boolean_field_2.id}": False,
                "order": "1.00000000000000000000",
            },
            {
                "id": 2,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": "240",
                f"field_{number_field_2.id}": "1000",
                f"field_{boolean_field.id}": False,
                f"field_{boolean_field_2.id}": True,
                "order": "2.00000000000000000000",
            },
        ]
    }
    if include_metadata:
        expected_response_body["metadata"] = {
            "updated_field_ids": [
                text_field.id,
                number_field.id,
                number_field_2.id,
                boolean_field.id,
                boolean_field_2.id,
            ]
        }
        url = f"{url}?include_metadata=true"

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body
    row_1 = model.objects.get(pk=1)
    row_2 = model.objects.get(pk=2)
    assert getattr(row_1, f"field_{text_field.id}") == "green"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"
    assert getattr(row_1, f"field_{number_field.id}") == 120
    assert getattr(row_2, f"field_{number_field.id}") == 240
    assert getattr(row_1, f"field_{number_field_2.id}") == 2000
    assert getattr(row_2, f"field_{number_field_2.id}") == 1000
    assert getattr(row_1, f"field_{boolean_field.id}") is True
    assert getattr(row_2, f"field_{boolean_field.id}") is False
    assert getattr(row_1, f"field_{boolean_field_2.id}") is False
    assert getattr(row_2, f"field_{boolean_field_2.id}") is True

    # Test creating rows without providing any values
    request_body_empty = {
        "items": [
            {},  # Empty values should use defaults
            {},
        ]
    }
    expected_response_body_empty = {
        "items": [
            {
                "id": 3,
                f"field_{text_field.id}": "white",  # text_default
                f"field_{number_field.id}": None,
                f"field_{number_field_2.id}": "1000",  # number_default=1000
                f"field_{boolean_field.id}": False,  # default without boolean_default
                f"field_{boolean_field_2.id}": True,  # boolean_default=True
                "order": "3.00000000000000000000",
            },
            {
                "id": 4,
                f"field_{text_field.id}": "white",
                f"field_{number_field.id}": None,
                f"field_{number_field_2.id}": "1000",
                f"field_{boolean_field.id}": False,
                f"field_{boolean_field_2.id}": True,
                "order": "4.00000000000000000000",
            },
        ]
    }

    if include_metadata:
        expected_response_body_empty["metadata"] = {
            "updated_field_ids": [
                text_field.id,
                number_field.id,
                number_field_2.id,
                boolean_field.id,
                boolean_field_2.id,
            ]
        }

    response = api_client.post(
        url,
        request_body_empty,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body_empty
    row_3 = model.objects.get(pk=3)
    row_4 = model.objects.get(pk=4)
    assert getattr(row_3, f"field_{number_field.id}") is None
    assert getattr(row_4, f"field_{number_field.id}") is None
    assert getattr(row_3, f"field_{number_field_2.id}") == 1000
    assert getattr(row_4, f"field_{number_field_2.id}") == 1000
    assert getattr(row_3, f"field_{boolean_field.id}") is False
    assert getattr(row_4, f"field_{boolean_field.id}") is False
    assert getattr(row_3, f"field_{boolean_field_2.id}") is True
    assert getattr(row_4, f"field_{boolean_field_2.id}") is True


@pytest.mark.django_db
@pytest.mark.api_rows
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_batch_create_rows_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{text_field.id}": "green",
            },
            {
                f"field_{text_field.id}": "yellow",
            },
        ]
    }

    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.force_create_rows"
    ) as mock_force_create_rows:
        # Create a proper OperationalError with a pgcode that indicates a deadlock

        mock_force_create_rows.side_effect = get_deadlock_error()
        response = api_client.post(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db(transaction=True)
@pytest.mark.api_rows
def test_batch_create_rows_with_disabled_webhook_events(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": 120,
                f"field_{boolean_field.id}": True,
            },
            {
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": 240,
                f"field_{boolean_field.id}": False,
            },
        ]
    }

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.post(
            f"{url}?send_webhook_events=false",
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

        assert response.status_code == HTTP_200_OK
        m.assert_not_called()


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_id_field_ignored(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                "id": 1,
                f"field_{text_field.id}": "green",
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
    assert len(list(model.objects.all())) == 2


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_different_fields_provided(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
            },
            {
                f"field_{text_field.id}": "yellow",
                f"field_{boolean_field.id}": True,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                "id": 1,
                f"field_{text_field.id}": "white",
                f"field_{number_field.id}": "120",
                f"field_{boolean_field.id}": False,
                "order": "1.00000000000000000000",
            },
            {
                "id": 2,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": None,
                f"field_{boolean_field.id}": True,
                "order": "2.00000000000000000000",
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
    row_1 = model.objects.get(pk=1)
    row_2 = model.objects.get(pk=2)
    assert getattr(row_1, f"field_{text_field.id}") == "white"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_user_field_names(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field_name = "Color"
    number_field_name = "Horsepower"
    boolean_field_name = "For sale"
    text_field = data_fixture.create_text_field(
        table=table, order=0, name=text_field_name, text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name=number_field_name
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name=boolean_field_name
    )
    model = table.get_model()
    url = (
        reverse("api:database:rows:batch", kwargs={"table_id": table.id})
        + "?user_field_names"
    )
    request_body = {
        "items": [
            {
                f"{number_field_name}": 120,
            },
            {
                f"{text_field_name}": "yellow",
                f"{boolean_field_name}": True,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"{text_field_name}": "white",
                f"{number_field_name}": "120",
                f"{boolean_field_name}": False,
                "order": "1.00000000000000000000",
            },
            {
                f"id": 2,
                f"{text_field_name}": "yellow",
                f"{number_field_name}": None,
                f"{boolean_field_name}": True,
                "order": "2.00000000000000000000",
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
    row_1 = model.objects.get(pk=1)
    row_2 = model.objects.get(pk=2)
    assert getattr(row_1, f"field_{text_field.id}") == "white"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_readonly_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    created_on_field = data_fixture.create_created_on_field(table=table)
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{created_on_field.id}": "2019-08-24T14:15:22Z",
            },
            {
                f"field_{created_on_field.id}": "2019-08-24T14:15:22Z",
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
    assert (
        response.json()["detail"]
        == "Field of type created_on is read only and should not be set manually."
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_ordering_last_rows(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    model = table.get_model()
    row_1 = model.objects.create(order=Decimal("1.00000000000000000000"))
    row_2 = model.objects.create(order=Decimal("2.00000000000000000000"))
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
            },
            {
                f"field_{number_field.id}": 240,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                "id": 3,
                f"field_{number_field.id}": "120",
                "order": "3.00000000000000000000",
            },
            {
                "id": 4,
                f"field_{number_field.id}": "240",
                "order": "4.00000000000000000000",
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
@pytest.mark.api_rows
def test_batch_create_rows_ordering_before_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    model = table.get_model()
    row_1 = model.objects.create(order=Decimal("1.00000000000000000000"))
    row_2 = model.objects.create(order=Decimal("2.00000000000000000000"))
    url = (
        reverse("api:database:rows:batch", kwargs={"table_id": table.id}) + "?before=2"
    )
    request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
            },
            {
                f"field_{number_field.id}": 240,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                "id": 3,
                f"field_{number_field.id}": "120",
                "order": "1.50000000000000000000",
            },
            {
                "id": 4,
                f"field_{number_field.id}": "240",
                "order": "1.66666666666666674068",
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
@pytest.mark.field_formula
@pytest.mark.api_rows
def test_batch_create_rows_dependent_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(table=table, order=1, name="Number")
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula="field('Number')*2",
        formula_type="number",
    )
    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
            },
            {
                f"field_{number_field.id}": 240,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"field_{formula_field.id}": f"{str(120*2)}",
            },
            {
                f"id": 2,
                f"field_{formula_field.id}": f"{str(240*2)}",
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
    assert is_dict_subset(expected_response_body, response.json())


@pytest.mark.django_db
def test_batch_create_rows_with_read_only_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=True
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.post(
        url,
        {
            "items": [
                {
                    f"field_{text_field.id}": "Green",
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json_row_1["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json_row_1["detail"]["items"]["0"][f"field_{text_field.id}"][0]["code"]
        == "read_only"
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_num_of_queries(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, jwt_token = data_fixture.create_user_and_token(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    # number field updating another table through link & formula
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )

    # common fields
    text_field = data_fixture.create_text_field(
        table=table_b, order=0, name="Color", text_default="white"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table_b, order=2, name="For sale"
    )

    # single and multiple select fields
    multiple_select_field = data_fixture.create_multiple_select_field(table=table_b)
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    single_select_field = data_fixture.create_single_select_field(table=table_b)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    single_select_field.select_options.set(
        [single_select_option_1, single_select_option_2]
    )

    # file field
    file_field = data_fixture.create_file_field(table=table_b)
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )

    # multiple collaborators
    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        table=table_b
    )

    # setup the tables
    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()
    row_b_3 = model_b.objects.create()
    row_b_4 = model_b.objects.create()
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    getattr(row_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_2, f"field_{link_field.id}").set([row_b_2.id])
    row_1.save()
    row_2.save()

    url = reverse("api:database:rows:batch", kwargs={"table_id": table_b.id})

    with CaptureQueriesContext(connection) as create_one_row_ctx:
        request_body = {
            "items": [
                {
                    f"field_{number_field.id}": 120,
                    f"field_{text_field.id}": "Text",
                    f"field_{boolean_field.id}": True,
                    f"field_{single_select_field.id}": single_select_option_1.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                    f"field_{file_field.id}": [
                        {"name": file1.name, "visible_name": "new name"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [
                        {"id": user.id},
                        {"id": user2.id},
                    ],
                },
            ]
        }
        response = api_client.post(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    with CaptureQueriesContext(connection) as create_multiple_rows_ctx:
        request_body2 = {
            "items": [
                {
                    f"field_{number_field.id}": 240,
                    f"field_{text_field.id}": "Text 2",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_1.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 2"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [
                        {"id": user.id},
                        {"id": user2.id},
                    ],
                },
                {
                    f"field_{number_field.id}": 240,
                    f"field_{text_field.id}": "Text 3",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_2.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 3"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [{"id": user.id}],
                },
                {
                    f"field_{number_field.id}": 500,
                    f"field_{text_field.id}": "Text 4",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_2.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 4"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [{"id": user2.id}],
                },
            ]
        }
        response = api_client.post(
            url,
            request_body2,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    assert len(create_one_row_ctx.captured_queries) == len(
        create_multiple_rows_ctx.captured_queries
    )


# Update


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_batch_update_rows_invalid_token(api_client, data_fixture, token_header):
    table = data_fixture.create_database_table()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_token_no_update_permission(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    no_update_perm_token = TokenHandler().create_token(
        user, table.database.workspace, "no permissions"
    )
    TokenHandler().update_token_permissions(
        user, no_update_perm_token, True, True, False, True
    )
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Token {no_update_perm_token.key}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_user_not_in_workspace(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table()
    request_body = {
        "items": [
            {
                f"id": 1,
                f"field_11": "green",
            },
        ]
    }
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_invalid_table_id(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    url = reverse("api:database:rows:batch", kwargs={"table_id": 14343})

    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_nonexistent_row_ids(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    invalid_row_ids = [32, 3465]
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{"id": id} for id in invalid_row_ids]}

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"
    assert response.json()["detail"] == f"The rows {str(invalid_row_ids)} do not exist."


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_batch_size_limit(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    num_rows = settings.BATCH_ROWS_SIZE_LIMIT + 1
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{"id": i} for i in range(num_rows)]}
    expected_error_detail = {
        "items": [
            {
                "code": "max_length",
                "error": f"Ensure this field has no more than {settings.BATCH_ROWS_SIZE_LIMIT} elements.",
            },
        ],
    }

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == expected_error_detail


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_no_payload(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {}

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["items"][0]["error"] == "This field is required."


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_field_validation(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{number_field.id}": 120,
            },
            {
                f"id": row_2.id,
                f"field_{number_field.id}": -200,
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
        response.json()["detail"]["items"]["1"][f"field_{number_field.id}"][0]["code"]
        == "min_value"
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_missing_row_ids(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{f"field_{number_field.id}": 123}]}

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response.json()["detail"]["items"]["0"]["id"][0]["error"]
        == "This field is required."
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_repeated_row_ids(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    repeated_row_id = 32
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {"items": [{"id": repeated_row_id} for i in range(2)]}

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ROW_IDS_NOT_UNIQUE"
    assert (
        response.json()["detail"]
        == f"The provided row ids {str([repeated_row_id])} are not unique."
    )


@pytest.mark.django_db
def test_batch_update_rows_with_read_only_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=True
    )

    model = table.get_model()
    row_1 = model.objects.create()

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {
            "items": [
                {
                    "id": row_1.id,
                    f"field_{text_field.id}": "Green",
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json_row_1["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json_row_1["detail"]["items"]["0"][f"field_{text_field.id}"][0]["code"]
        == "read_only"
    )


@pytest.mark.parametrize("include_metadata", [True, False])
@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows(api_client, data_fixture, include_metadata):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": 120,
                f"field_{boolean_field.id}": True,
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": 240,
                f"field_{boolean_field.id}": False,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": "120",
                f"field_{boolean_field.id}": True,
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": "240",
                f"field_{boolean_field.id}": False,
                "order": "1.00000000000000000000",
            },
        ]
    }
    if include_metadata:
        expected_response_body["metadata"] = {
            "cascade_update": {"field_ids": [], "rows": []},
            "updated_field_ids": unordered(
                [text_field.id, number_field.id, boolean_field.id]
            ),
        }
        url = f"{url}?include_metadata=true"

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "green"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"
    assert getattr(row_1, f"field_{boolean_field.id}") is True
    assert getattr(row_2, f"field_{boolean_field.id}") is False


@pytest.mark.parametrize("include_metadata", [True, False])
@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_with_different_fields(
    api_client, data_fixture, include_metadata
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{boolean_field.id}": True,
            },
            {
                f"id": row_2.id,
                f"field_{number_field.id}": 240,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": None,
                f"field_{boolean_field.id}": True,
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "white",
                f"field_{number_field.id}": "240",
                f"field_{boolean_field.id}": False,
                "order": "1.00000000000000000000",
            },
        ]
    }
    if include_metadata:
        expected_response_body["metadata"] = {
            "cascade_update": {"field_ids": [], "rows": []},
            "updated_field_ids": unordered(
                [text_field.id, number_field.id, boolean_field.id]
            ),
        }
        url = f"{url}?include_metadata=true"

    response = api_client.patch(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == expected_response_body
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "green"
    assert getattr(row_2, f"field_{text_field.id}") == "white"  # default val
    assert getattr(row_1, f"field_{boolean_field.id}") is True
    assert getattr(row_2, f"field_{boolean_field.id}") is False


@pytest.mark.django_db
@pytest.mark.api_rows
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_batch_update_rows_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                "id": row_1.id,
                f"field_{text_field.id}": "green",
            },
            {
                "id": row_2.id,
                f"field_{text_field.id}": "yellow",
            },
        ]
    }
    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.force_update_rows"
    ) as mock_force_update_rows:
        mock_force_update_rows.side_effect = get_deadlock_error()

        response = api_client.patch(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db(transaction=True)
@pytest.mark.api_rows
def test_batch_update_rows_with_disabled_webhook_events(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{number_field.id}": 120,
                f"field_{boolean_field.id}": True,
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": 240,
                f"field_{boolean_field.id}": False,
            },
        ]
    }

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.patch(
            f"{url}?send_webhook_events=false",
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
        assert response.status_code == HTTP_200_OK
        m.assert_not_called()


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_last_modified_field(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    last_modified_field = data_fixture.create_last_modified_field(
        table=table, order=1, date_include_time=True
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "green",
                f"field_{last_modified_field.id}": "2022-04-18T00:00:00Z",
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{last_modified_field.id}": "2022-04-18T00:00:00Z",
                "order": "1.00000000000000000000",
            },
        ]
    }

    with freeze_time("2022-04-18 00:00:00"):
        jwt_token = data_fixture.generate_token(user)
        response = api_client.patch(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

        assert response.status_code == HTTP_200_OK
        assert response.json() == expected_response_body


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_different_fields_provided(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{number_field.id}": 120,
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{boolean_field.id}": True,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{text_field.id}": "white",
                f"field_{number_field.id}": "120",
                f"field_{boolean_field.id}": False,
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"field_{text_field.id}": "yellow",
                f"field_{number_field.id}": None,
                f"field_{boolean_field.id}": True,
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
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "white"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_different_manytomany_provided(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    table2 = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, name="primary1", primary=True)
    primary2 = data_fixture.create_text_field(
        table=table2, name="primary2", primary=True
    )

    link_row_field_1 = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="link1",
        link_row_table=table2,
    )
    link_row_field_2 = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="link2",
        link_row_table=table2,
    )

    model = table.get_model(attribute_names=True)
    model_1_row_1 = model.objects.create(primary1="row 1")
    model_1_row_2 = model.objects.create(primary1="row 2")
    model_1_row_3 = model.objects.create(primary1="row 3")

    model2 = table2.get_model(attribute_names=True)
    model_2_row_1 = model2.objects.create(primary2="row A")
    model_2_row_2 = model2.objects.create(primary2="row B")

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {
            "items": [
                {
                    f"id": model_1_row_1.id,
                    f"field_{link_row_field_1.id}": [model_2_row_1.id],
                },
                {
                    f"id": model_1_row_2.id,
                    f"field_{link_row_field_2.id}": [model_2_row_2.id],
                },
                {
                    f"id": model_1_row_3.id,
                    f"field_{link_row_field_1.id}": [
                        model_2_row_1.id,
                        model_2_row_2.id,
                    ],
                    f"field_{link_row_field_2.id}": [
                        model_2_row_1.id,
                        model_2_row_2.id,
                    ],
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 1",
                f"field_{link_row_field_1.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()}
                ],
                f"field_{link_row_field_2.id}": [],
            },
            {
                "id": 2,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 2",
                f"field_{link_row_field_1.id}": [],
                f"field_{link_row_field_2.id}": [
                    {"id": 2, "value": "row B", "order": AnyStr()}
                ],
            },
            {
                "id": 3,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 3",
                f"field_{link_row_field_1.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()},
                    {"id": 2, "value": "row B", "order": AnyStr()},
                ],
                f"field_{link_row_field_2.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()},
                    {"id": 2, "value": "row B", "order": AnyStr()},
                ],
            },
        ]
    }

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {
            "items": [
                {
                    f"id": model_1_row_1.id,
                    f"field_{link_row_field_2.id}": [model_2_row_1.id],
                },
                {
                    f"id": model_1_row_2.id,
                    f"field_{link_row_field_1.id}": [model_2_row_2.id],
                },
                {f"id": model_1_row_3.id},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 1",
                f"field_{link_row_field_1.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()}
                ],
                f"field_{link_row_field_2.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()}
                ],
            },
            {
                "id": 2,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 2",
                f"field_{link_row_field_1.id}": [
                    {"id": 2, "value": "row B", "order": AnyStr()}
                ],
                f"field_{link_row_field_2.id}": [
                    {"id": 2, "value": "row B", "order": AnyStr()}
                ],
            },
            {
                "id": 3,
                "order": "1.00000000000000000000",
                f"field_{primary.id}": "row 3",
                f"field_{link_row_field_1.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()},
                    {"id": 2, "value": "row B", "order": AnyStr()},
                ],
                f"field_{link_row_field_2.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()},
                    {"id": 2, "value": "row B", "order": AnyStr()},
                ],
            },
        ]
    }


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_user_field_names(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field_name = "Color"
    number_field_name = "Horsepower"
    boolean_field_name = "For sale"
    text_field = data_fixture.create_text_field(
        table=table, order=0, name=text_field_name, text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name=number_field_name
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name=boolean_field_name
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = (
        reverse("api:database:rows:batch", kwargs={"table_id": table.id})
        + "?user_field_names"
    )
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"{number_field_name}": 120,
            },
            {
                f"id": row_2.id,
                f"{text_field_name}": "yellow",
                f"{boolean_field_name}": True,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"{text_field_name}": "white",
                f"{number_field_name}": "120",
                f"{boolean_field_name}": False,
                "order": "1.00000000000000000000",
            },
            {
                f"id": row_2.id,
                f"{text_field_name}": "yellow",
                f"{number_field_name}": None,
                f"{boolean_field_name}": True,
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
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "white"
    assert getattr(row_2, f"field_{text_field.id}") == "yellow"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_readonly_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    created_on_field = data_fixture.create_created_on_field(table=table)
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{created_on_field.id}": "2019-08-24T14:15:22Z",
            },
            {
                f"id": row_2.id,
                f"field_{created_on_field.id}": "2019-08-24T14:15:22Z",
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
    assert (
        response.json()["detail"]
        == "Field of type created_on is read only and should not be set manually."
    )


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_dependent_fields(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(table=table, order=1, name="Number")
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula="field('Number')*2",
        formula_type="number",
    )
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    request_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{number_field.id}": 120,
            },
            {
                f"id": row_2.id,
                f"field_{number_field.id}": 240,
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": row_1.id,
                f"field_{formula_field.id}": f"{str(120*2)}",
            },
            {
                f"id": row_2.id,
                f"field_{formula_field.id}": f"{str(240*2)}",
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


@pytest.mark.django_db
@pytest.mark.field_formula
@pytest.mark.api_rows
def test_batch_update_rows_dependent_fields_diff_table(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    getattr(row_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_2, f"field_{link_field.id}").set([row_b_2.id])
    row_1.save()
    row_2.save()

    url = reverse("api:database:rows:batch", kwargs={"table_id": table_b.id})
    request_body = {
        "items": [
            {
                f"id": row_b_1.id,
                f"field_{number_field.id}": 120,
            },
            {
                f"id": row_b_2.id,
                f"field_{number_field.id}": 240,
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
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{formula_field.id}")[0]["value"] == 120 * 2
    assert getattr(row_1, f"field_{formula_field.id}")[1]["value"] == 240 * 2
    assert getattr(row_2, f"field_{formula_field.id}")[0]["value"] == 240 * 2


@pytest.mark.django_db
@pytest.mark.field_formula
@pytest.mark.api_rows
def test_batch_create_rows_dependent_fields_lookup(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    lookup_formula = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="Sum of looked up number",
        formula=f"sum(lookup('{link_field.name}', 'Number'))",
    )
    assert lookup_formula.formula_type == "number"
    row_id_formula = FieldHandler().create_field(
        user,
        table_a,
        "formula",
        name="Row ID",
        formula=f"row_id()",
    )
    assert row_id_formula.formula_type == "number"
    model_a = table_a.get_model()
    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create(**{f"field_{number_field.id}": 1})
    row_b_2 = model_b.objects.create(**{f"field_{number_field.id}": 1})

    url = reverse("api:database:rows:batch", kwargs={"table_id": table_a.id})
    request_body = {
        "items": [
            {
                f"field_{link_field.id}": [row_b_1.id, row_b_2.id],
            },
            {
                f"field_{link_field.id}": [row_b_1.id],
            },
            {
                f"field_{link_field.id}": [],
            },
        ]
    }
    expected_response_body = {
        "items": [
            {
                f"id": 1,
                f"field_{lookup_formula.id}": "2",
                f"field_{row_id_formula.id}": "1",
            },
            {
                f"id": 2,
                f"field_{lookup_formula.id}": "1",
                f"field_{row_id_formula.id}": "2",
            },
            {
                f"id": 3,
                f"field_{lookup_formula.id}": "0",
                f"field_{row_id_formula.id}": "3",
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
    assert is_dict_subset(expected_response_body, response.json())


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_update_rows_num_of_queries(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    user, jwt_token = data_fixture.create_user_and_token(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    # number field updating another table through link & formula
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )

    # common fields
    text_field = data_fixture.create_text_field(
        table=table_b, order=0, name="Color", text_default="white"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table_b, order=2, name="For sale"
    )

    # single and multiple select fields
    multiple_select_field = data_fixture.create_multiple_select_field(table=table_b)
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    single_select_field = data_fixture.create_single_select_field(table=table_b)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    single_select_field.select_options.set(
        [single_select_option_1, single_select_option_2]
    )

    # file field
    file_field = data_fixture.create_file_field(table=table_b)
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )

    # multiple collaborators
    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        table=table_b
    )

    # last modified is readonly but the auto update shouldn't produce n+1 queries
    last_modified_field = data_fixture.create_last_modified_field(
        table=table_b, date_include_time=True
    )

    # setup the tables
    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()
    row_b_3 = model_b.objects.create()
    row_b_4 = model_b.objects.create()
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    getattr(row_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_2, f"field_{link_field.id}").set([row_b_2.id])
    row_1.save()
    row_2.save()

    url = reverse("api:database:rows:batch", kwargs={"table_id": table_b.id})

    related_link_field = link_field.link_row_related_field
    with CaptureQueriesContext(connection) as update_one_row_ctx:
        request_body = {
            "items": [
                {
                    f"id": row_b_1.id,
                    f"field_{related_link_field.id}": [row_1.id],
                    f"field_{number_field.id}": 120,
                    f"field_{text_field.id}": "Text",
                    f"field_{boolean_field.id}": True,
                    f"field_{single_select_field.id}": single_select_option_1.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                    f"field_{file_field.id}": [
                        {"name": file1.name, "visible_name": "new name"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [
                        {"id": user.id},
                        {"id": user2.id},
                    ],
                },
            ]
        }
        response = api_client.patch(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    with CaptureQueriesContext(connection) as update_multiple_rows_ctx:
        request_body2 = {
            "items": [
                {
                    f"id": row_b_2.id,
                    f"field_{related_link_field.id}": [row_1.id],
                    f"field_{number_field.id}": 240,
                    f"field_{text_field.id}": "Text 2",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_1.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 2"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [
                        {"id": user.id},
                        {"id": user2.id},
                    ],
                },
                {
                    f"id": row_b_3.id,
                    f"field_{related_link_field.id}": [row_2.id],
                    f"field_{number_field.id}": 240,
                    f"field_{text_field.id}": "Text 3",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_2.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 3"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [{"id": user.id}],
                },
                {
                    f"id": row_b_4.id,
                    f"field_{related_link_field.id}": [row_1.id, row_2.id],
                    f"field_{number_field.id}": 500,
                    f"field_{text_field.id}": "Text 4",
                    f"field_{boolean_field.id}": False,
                    f"field_{single_select_field.id}": single_select_option_2.id,
                    f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                    f"field_{file_field.id}": [
                        {"name": file2.name, "visible_name": "new name 4"}
                    ],
                    f"field_{multiple_collaborators_field.id}": [{"id": user2.id}],
                },
            ]
        }
        response = api_client.patch(
            url,
            request_body2,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    assert len(update_one_row_ctx.captured_queries) == len(
        update_multiple_rows_ctx.captured_queries
    )


# Delete


@pytest.mark.django_db
@pytest.mark.api_rows
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_batch_delete_rows_invalid_token(api_client, data_fixture, token_header):
    table = data_fixture.create_database_table()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_delete_rows_token_no_delete_permission(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    no_create_perm_token = TokenHandler().create_token(
        user, table.database.workspace, "no permissions"
    )
    TokenHandler().update_token_permissions(
        user, no_create_perm_token, True, True, True, False
    )
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        {"items": [1, 2]},
        format="json",
        HTTP_AUTHORIZATION=f"Token {no_create_perm_token.key}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_delete_rows_user_not_in_workspace(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table()
    request_body = {"items": [22]}
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_delete_rows_invalid_table_id(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": 14343})

    response = api_client.post(
        url,
        {"items": [1, 2]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_delete_rows_trash_them(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    row_3 = model.objects.create()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})
    request_body = {"items": [row_1.id, row_2.id]}

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert getattr(row_1, "trashed") is True
    assert getattr(row_2, "trashed") is True
    assert getattr(row_3, "trashed") is False


@pytest.mark.django_db
@pytest.mark.api_rows
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_batch_delete_rows_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})
    request_body = {"items": [row_1.id, row_2.id]}

    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.delete_rows"
    ) as mock_delete_rows:
        mock_delete_rows.side_effect = get_deadlock_error()
        response = api_client.post(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db
def test_cannot_batch_delete_rows_with_data_sync(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_ical_data_sync(table=table)

    model = table.get_model()
    row_1 = model.objects.create()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})
    request_body = {"items": [row_1.id]}

    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_ROWS_IN_TABLE"


@pytest.mark.django_db
@pytest.mark.field_formula
@pytest.mark.api_rows
def test_batch_delete_rows_dependent_fields_diff_table(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    getattr(row_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_2, f"field_{link_field.id}").set([row_b_2.id])
    row_1.save()
    row_2.save()

    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table_b.id})
    request_body = {
        "items": [
            row_b_1.id,
            row_b_2.id,
        ]
    }
    response = api_client.post(
        url,
        request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    assert getattr(row_1, f"field_{formula_field.id}") == []
    assert getattr(row_2, f"field_{formula_field.id}") == []


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_delete_rows_num_of_queries(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    # number field updating another table through link & formula
    number_field = data_fixture.create_number_field(
        table=table_b, order=1, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )

    # common fields
    text_field = data_fixture.create_text_field(
        table=table_b, order=0, name="Color", text_default="white"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table_b, order=2, name="For sale"
    )

    # single and multiple select fields
    multiple_select_field = data_fixture.create_multiple_select_field(table=table_b)
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    single_select_field = data_fixture.create_single_select_field(table=table_b)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 2",
        color="blue",
    )
    single_select_field.select_options.set(
        [single_select_option_1, single_select_option_2]
    )

    # file field
    file_field = data_fixture.create_file_field(table=table_b)
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )

    # setup the tables
    model_b = table_b.get_model()
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    # create rows
    url = reverse("api:database:rows:batch", kwargs={"table_id": table_b.id})
    create_rows_request_body = {
        "items": [
            {
                f"field_{number_field.id}": 120,
                f"field_{text_field.id}": "Text",
                f"field_{boolean_field.id}": True,
                f"field_{single_select_field.id}": single_select_option_1.id,
                f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                f"field_{file_field.id}": [
                    {"name": file1.name, "visible_name": "new name"}
                ],
            },
            {
                f"field_{number_field.id}": 240,
                f"field_{text_field.id}": "Text 2",
                f"field_{boolean_field.id}": False,
                f"field_{single_select_field.id}": single_select_option_1.id,
                f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                f"field_{file_field.id}": [
                    {"name": file2.name, "visible_name": "new name 2"}
                ],
            },
            {
                f"field_{number_field.id}": 240,
                f"field_{text_field.id}": "Text 3",
                f"field_{boolean_field.id}": False,
                f"field_{single_select_field.id}": single_select_option_2.id,
                f"field_{multiple_select_field.id}": [multi_select_option_2.id],
                f"field_{file_field.id}": [
                    {"name": file2.name, "visible_name": "new name 3"}
                ],
            },
            {
                f"field_{number_field.id}": 500,
                f"field_{text_field.id}": "Text 4",
                f"field_{boolean_field.id}": False,
                f"field_{single_select_field.id}": single_select_option_2.id,
                f"field_{multiple_select_field.id}": [multi_select_option_1.id],
                f"field_{file_field.id}": [
                    {"name": file2.name, "visible_name": "new name 4"}
                ],
            },
        ]
    }
    response = api_client.post(
        url,
        create_rows_request_body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    # link rows table -> table_b
    getattr(row_1, f"field_{link_field.id}").set([1, 2, 3, 4])
    getattr(row_2, f"field_{link_field.id}").set([2, 3])
    row_1.save()
    row_2.save()

    delete_url = reverse(
        "api:database:rows:batch-delete", kwargs={"table_id": table_b.id}
    )

    with CaptureQueriesContext(connection) as delete_one_row_ctx:
        request_body = {"items": [1]}
        response = api_client.post(
            delete_url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    with CaptureQueriesContext(connection) as delete_multiple_rows_ctx:
        request_body = {"items": [2, 3, 4]}
        response = api_client.post(
            delete_url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    assert len(delete_one_row_ctx.captured_queries) == len(
        delete_multiple_rows_ctx.captured_queries
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.api_rows
def test_batch_delete_rows_disabled_webhook_events(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    model.objects.create()
    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})
    request_body = {"items": [row_1.id, row_2.id]}

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.post(
            f"{url}?send_webhook_events=false",
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        m.assert_not_called()


@pytest.mark.django_db
@pytest.mark.api_rows
def test_batch_create_rows_single_select_default(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    option_1 = data_fixture.create_select_option(
        field=option_field, value="1", color="blue"
    )
    option_2 = data_fixture.create_select_option(
        field=option_field, value="2", color="red"
    )

    field_handler = FieldHandler()
    option_field = field_handler.update_field(
        user=user, field=option_field, single_select_default=option_1.id
    )

    model = table.get_model()
    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    request_body = {
        "items": [
            {
                f"field_{option_field.id}": option_2.id,
            },
            {
                # Not providing a value should use the default (active)
            },
        ]
    }

    expected_response_body = {
        "items": [
            {
                "id": 1,
                f"field_{option_field.id}": {
                    "id": option_2.id,
                    "value": "2",
                    "color": "red",
                },
                "order": "1.00000000000000000000",
            },
            {
                "id": 2,
                f"field_{option_field.id}": {
                    "id": option_1.id,
                    "value": "1",
                    "color": "blue",
                },
                "order": "2.00000000000000000000",
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

    row_1 = model.objects.get(pk=1)
    row_2 = model.objects.get(pk=2)
    assert getattr(row_1, f"field_{option_field.id}").id == option_2.id
    assert getattr(row_2, f"field_{option_field.id}").id == option_1.id
