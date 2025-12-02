import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import quote

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
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import (
    AnyInt,
    AnyStr,
    assert_undo_redo_actions_are_valid,
    setup_interesting_test_table,
)
from tests.baserow.contrib.database.utils import (
    autonumber_field_factory,
    get_deadlock_error,
    uuid_field_factory,
)


@pytest.mark.django_db
def test_list_rows(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_number_field(name="Price", table=table)
    field_3 = data_fixture.create_text_field()
    field_4 = data_fixture.create_boolean_field(name="InStock", table=table)
    grid_view = data_fixture.create_grid_view(user=user, table=table)
    unrelated_view = data_fixture.create_grid_view(user=user, table=table_2)
    data_fixture.create_view_filter(
        view=grid_view, user=user, field=field_1, value="Product 1"
    )

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, False, True, True)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="Product 1", price=50, order=Decimal("1"))
    row_2 = model.objects.create(name="Product 2/3", price=100, order=Decimal("2"))
    row_3 = model.objects.create(name="Product 3", price=150, order=Decimal("3"))
    row_4 = model.objects.create(name="Last product", price=200, order=Decimal("4"))

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": 999999}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table_2.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    user.is_active = False
    user.save()
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_USER_NOT_ACTIVE"
    user.is_active = True
    user.save()

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][0][f"field_{field_1.id}"] == "Product 1"
    assert response_json["results"][0][f"field_{field_2.id}"] == "50"
    assert response_json["results"][0]["order"] == "1.00000000000000000000"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?include=field_{field_1.id},field_{field_3.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert f"field_{field_1.id}" in response_json["results"][0]
    assert f"field_{field_2.id}" not in response_json["results"][0]
    assert f"field_{field_3.id}" not in response_json["results"][0]

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?exclude=field_{field_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert f"field_{field_1.id}" not in response_json["results"][0]
    assert f"field_{field_2.id}" in response_json["results"][0]

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?size=2&page=1", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?size=2&page=2", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_3.id
    assert response_json["results"][1]["id"] == row_4.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?size=2&page=3", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == []

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?size=201", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_PAGE_SIZE_LIMIT"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?search=Product 1", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_1.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?search=4", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_4.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?search=3", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_2.id
    assert response_json["results"][1]["id"] == row_3.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?search=200", format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_4.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=field_999999",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"
    assert response_json["detail"] == (
        "The field field_999999 was not found in the table."
    )

    number_field_type = field_type_registry.get("number")
    old_can_order_by = number_field_type._can_order_by_types
    number_field_type._can_order_by_types = []
    invalidate_table_in_model_cache(table.id)
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=-field_{field_2.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"
    assert response_json["detail"] == (
        f"It is not possible to order by field_{field_2.id} using sort type default "
        f"because the field type number does not support it."
    )
    number_field_type._can_order_by_types = old_can_order_by
    invalidate_table_in_model_cache(table.id)

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=-field_{field_2.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 4
    assert response_json["results"][0]["id"] == row_4.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_2.id
    assert response_json["results"][3]["id"] == row_1.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [f"filter__field_9999999__contains=last"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [f"filter__field_{field_4.id}__contains=100"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [f"filter__field_{field_2.id}__INVALID=100"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"
    assert response_json["detail"] == "The view filter type INVALID doesn't exist."

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__field_{field_1.id}__contains=last",
        f"filter__field_{field_2.id}__equal=200",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_4.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__field_{field_1.id}__contains=last",
        f"filter__field_{field_2.id}__higher_than=110",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_3.id
    assert response_json["results"][1]["id"] == row_4.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__field_{field_1.id}__equal=Product 1",
        f"filter__field_{field_1.id}__equal=Product 3",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_3.id

    row_2.order = Decimal("999")
    row_2.save()
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert len(response_json["results"]) == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_4.id
    assert response_json["results"][3]["id"] == row_2.id

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": grid_view.id},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_1.id

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": -1},
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": unrelated_view.id},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_list_rows_order_by_type(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    select_1 = data_fixture.create_single_select_field(name="Select", table=table)
    option_1 = data_fixture.create_select_option(field=select_1, value="A", order=3)
    option_2 = data_fixture.create_select_option(field=select_1, value="B", order=1)
    option_3 = data_fixture.create_select_option(field=select_1, value="C", order=2)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="Product 1", select_id=option_1.id)
    row_2 = model.objects.create(name="Product 2", select_id=option_2.id)
    row_3 = model.objects.create(name="Product 3", select_id=option_3.id)

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=-field_{field_1.id}[unknown]",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"
    assert response_json["detail"] == (
        f"It is not possible to order by field_{field_1.id} using sort type unknown "
        f"because the field type text does not support it."
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=field_{field_1.id}[default]",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id
    assert response_json["results"][2]["id"] == row_3.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=-field_{field_1.id}[default]",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"][0]["id"] == row_3.id
    assert response_json["results"][1]["id"] == row_2.id
    assert response_json["results"][2]["id"] == row_1.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=field_{select_1.id}[order]",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"][0]["id"] == row_2.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_1.id


@pytest.mark.django_db
def test_list_rows_adhoc_filtering_query_param_null_character(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="normal")
    first_row = RowHandler().create_row(
        user, table, values={"normal": "a"}, user_field_names=True
    )
    RowHandler().create_row(user, table, values={"normal": "b"}, user_field_names=True)

    str_with_null_character = "a\0"
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [f"filter__field_{text_field.id}__contains={str_with_null_character}"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id


@pytest.mark.django_db
def test_list_rows_user_field_names(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_text_field(name="field_123456", table=table)
    field_3 = data_fixture.create_text_field(name="field_üńîćødë", table=table)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(
        name="Product 1", field123456="1st product", order=Decimal("1")
    )
    row_2 = model.objects.create(
        name="Product 2", field123456="2nd product", order=Decimal("2")
    )
    row_3 = model.objects.create(
        name="Product 3", field123456="3rd product", order=Decimal("3")
    )
    row_4 = model.objects.create(
        name="Product 4", fieldüńîćødë="Unicode product", order=Decimal("4")
    )

    # Test with field names
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__{field_1.name}__equal=Product 1",
        f"filter__{field_1.name}__equal=Product 2",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?user_field_names=true&{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id

    # Test with field_id and user_field_names=true
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__field_{field_1.id}__equal=Product 1",
        f"filter__field_{field_1.id}__equal=Product 2",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?user_field_names=true&{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id

    # Test with field name "field_123456" and user_field_names=true
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__{field_2.name}__equal=3rd product",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?user_field_names=true&{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_3.id

    # Test with field name "field_üńîćødë" and user_field_names=true
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    get_params = [
        f"filter__{field_3.name}__equal=Unicode product",
        "filter_type=or",
    ]
    response = api_client.get(
        f'{url}?user_field_names=true&{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_4.id


@pytest.mark.django_db
def test_list_rows_sort_query_overrides_existing_sort(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    grid_view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_sort(
        user=user, view=grid_view, field=field_1, order="DESC"
    )

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="a")
    row_2 = model.objects.create(name="b")
    row_3 = model.objects.create(name="c")
    row_4 = model.objects.create(name="d")

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": grid_view.id, "order_by": field_1.id},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"][0]["id"] == row_1.id


@pytest.mark.django_db
def test_list_rows_filter_stacks_with_existing_filter(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_number_field(name="Number", table=table)
    grid_view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_filter(
        view=grid_view, user=user, field=field_1, value="ab", type="contains"
    )

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="a", number="1")
    row_2 = model.objects.create(name="ab", number="2")
    row_3 = model.objects.create(name="abc", number="3")
    row_4 = model.objects.create(name="abcd", number="1")

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": grid_view.id, f"filter__field_{field_2.id}__contains": "1"},
    )

    # The only row that matches both filters is row_4
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_4.id


@pytest.mark.django_db
def test_list_rows_filter_filters_query_param(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_number_field(name="Number", table=table)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="a", number="1")
    row_2 = model.objects.create(name="ab", number="2")
    row_3 = model.objects.create(name="abc", number="3")
    row_4 = model.objects.create(name="abcd", number="1")

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": field_1.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": field_2.id,
                        "type": "equal",
                        "value": 3,
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_3.id


@pytest.mark.django_db
def test_list_rows_filter_filters_query_param_with_user_field_names(
    data_fixture, api_client
):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_number_field(name="Number", table=table)

    model = table.get_model(attribute_names=True)
    row_1 = model.objects.create(name="a", number="1")
    row_2 = model.objects.create(name="ab", number="2")
    row_3 = model.objects.create(name="abc", number="3")
    row_4 = model.objects.create(name="abcd", number="1")

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": "Name",
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": "Number",
                        "type": "equal",
                        "value": 3,
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters), "user_field_names=true"]
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    response = api_client.get(
        f'{url}?{"&".join(get_params)}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_3.id


@pytest.mark.parametrize("user_field_names", [False, True])
@pytest.mark.django_db
def test_list_rows_join_lookup(api_client, data_fixture, user_field_names):
    user, token = data_fixture.create_user_and_token(email="test@example.com")
    table = data_fixture.create_database_table(user=user)
    (
        linked_table,
        _,
        linked_row,
        linked_blank_row,
        context,
    ) = setup_interesting_test_table(data_fixture, user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=linked_table,
    )
    row = RowHandler().create_row(
        user,
        table,
        values={f"field_{link_row_field.id}": [linked_row.id, linked_blank_row.id]},
    )
    linked_table_model = linked_table.get_model()

    def get_field_ref(user_field_name: str) -> str:
        field_obj = linked_table_model.get_field_object_by_user_field_name(
            user_field_name
        )
        return (
            field_obj["field"].name
            if user_field_names
            else f"field_{field_obj['field'].id}"
        )

    expected_results_by_field_name = {
        "text": {"blank": None, "row": "text"},
        "long_text": {"blank": None, "row": "long_text"},
        "url": {"blank": "", "row": "https://www.google.com"},
        "email": {"blank": "", "row": "test@example.com"},
        "negative_int": {"blank": None, "row": "-1"},
        "positive_int": {"blank": None, "row": "1"},
        "negative_decimal": {"blank": None, "row": "-1.2"},
        "positive_decimal": {"blank": None, "row": "1.2"},
        "rating": {"blank": 0, "row": 3},
        "boolean": {"blank": False, "row": True},
        "datetime_us": {
            "blank": None,
            "row": "2020-02-01T01:23:00Z",
        },
        "date_us": {
            "blank": None,
            "row": "2020-02-01",
        },
        "datetime_eu": {
            "blank": None,
            "row": "2020-02-01T01:23:00Z",
        },
        "date_eu": {
            "blank": None,
            "row": "2020-02-01",
        },
        "datetime_eu_tzone_visible": {
            "blank": None,
            "row": "2020-02-01T01:23:00Z",
        },
        "datetime_eu_tzone_hidden": {
            "blank": None,
            "row": "2020-02-01T01:23:00Z",
        },
        "last_modified_datetime_us": {
            "blank": linked_blank_row.updated_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.updated_on.isoformat().replace("+00:00", "Z"),
        },
        "last_modified_date_us": {
            "blank": linked_blank_row.updated_on.strftime("%Y-%m-%d"),
            "row": linked_row.updated_on.strftime("%Y-%m-%d"),
        },
        "last_modified_datetime_eu": {
            "blank": linked_blank_row.updated_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.updated_on.isoformat().replace("+00:00", "Z"),
        },
        "last_modified_date_eu": {
            "blank": linked_blank_row.updated_on.strftime("%Y-%m-%d"),
            "row": linked_row.updated_on.strftime("%Y-%m-%d"),
        },
        "last_modified_datetime_eu_tzone": {
            "blank": linked_blank_row.updated_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.updated_on.isoformat().replace("+00:00", "Z"),
        },
        "created_on_datetime_us": {
            "blank": linked_blank_row.created_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.created_on.isoformat().replace("+00:00", "Z"),
        },
        "created_on_date_us": {
            "blank": linked_blank_row.created_on.strftime("%Y-%m-%d"),
            "row": linked_row.created_on.strftime("%Y-%m-%d"),
        },
        "created_on_datetime_eu": {
            "blank": linked_blank_row.created_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.created_on.isoformat().replace("+00:00", "Z"),
        },
        "created_on_date_eu": {
            "blank": linked_blank_row.created_on.strftime("%Y-%m-%d"),
            "row": linked_row.created_on.strftime("%Y-%m-%d"),
        },
        "created_on_datetime_eu_tzone": {
            "blank": linked_blank_row.created_on.isoformat().replace("+00:00", "Z"),
            "row": linked_row.created_on.isoformat().replace("+00:00", "Z"),
        },
        "last_modified_by": {
            "blank": {"id": user.id, "name": user.first_name},
            "row": {"id": user.id, "name": user.first_name},
        },
        "created_by": {
            "blank": {"id": user.id, "name": user.first_name},
            "row": {"id": user.id, "name": user.first_name},
        },
        "duration_hm": {
            "blank": None,
            "row": 3660.0,
        },
        "duration_hms": {
            "blank": None,
            "row": 3666.0,
        },
        "duration_hms_s": {
            "blank": None,
            "row": 3666.6,
        },
        "duration_hms_ss": {
            "blank": None,
            "row": 3666.66,
        },
        "duration_hms_sss": {
            "blank": None,
            "row": 3666.666,
        },
        "duration_dh": {
            "blank": None,
            "row": 90000.0,
        },
        "duration_dhm": {
            "blank": None,
            "row": 90060.0,
        },
        "duration_dhms": {
            "blank": None,
            "row": 90066.0,
        },
        "file": {
            "blank": [],
            "row": [
                {
                    "image_height": None,
                    "image_width": None,
                    "is_image": False,
                    "mime_type": "text/plain",
                    "name": "hashed_name.txt",
                    "size": 100,
                    "thumbnails": None,
                    "uploaded_at": "2020-02-01T01:23:00+00:00",
                    "url": "http://localhost:8000/media/user_files/hashed_name.txt",
                    "visible_name": "a.txt",
                },
                {
                    "image_height": None,
                    "image_width": None,
                    "is_image": False,
                    "mime_type": "text/plain",
                    "name": "other_name.txt",
                    "size": 100,
                    "thumbnails": None,
                    "uploaded_at": "2020-02-01T01:23:00+00:00",
                    "url": "http://localhost:8000/media/user_files/other_name.txt",
                    "visible_name": "b.txt",
                },
            ],
        },
        "single_select": {
            "blank": None,
            "row": {"color": "red", "id": AnyInt(), "value": "A"},
        },
        "multiple_select": {
            "blank": [],
            "row": unordered(
                [
                    {"color": "yellow", "id": AnyInt(), "value": "D"},
                    {"color": "orange", "id": AnyInt(), "value": "C"},
                    {"color": "green", "id": AnyInt(), "value": "E"},
                ]
            ),
        },
        "multiple_collaborators": {
            "blank": [],
            "row": [
                {"id": AnyInt(), "name": context["user2"].first_name},
                {"id": AnyInt(), "name": context["user3"].first_name},
            ],
        },
        "phone_number": {
            "blank": "",
            "row": "+4412345678",
        },
        "formula_text": {
            "blank": "test FORMULA",
            "row": "test FORMULA",
        },
        "formula_int": {
            "blank": "1",
            "row": "1",
        },
        "formula_bool": {
            "blank": True,
            "row": True,
        },
        "formula_decimal": {
            "blank": "33.3333333333",
            "row": "33.3333333333",
        },
        "formula_dateinterval": {
            "blank": 86400.0,
            "row": 86400.0,
        },
        "formula_date": {
            "blank": "2020-01-01",
            "row": "2020-01-01",
        },
        "formula_singleselect": {
            "blank": None,
            "row": {"color": "red", "id": AnyInt(), "value": "A"},
        },
        "formula_email": {
            "blank": "",
            "row": "test@example.com",
        },
        "formula_link_with_label": {
            "blank": {"label": "label", "url": "https://google.com"},
            "row": {"label": "label", "url": "https://google.com"},
        },
        "formula_link_url_only": {
            "blank": {"label": None, "url": "https://google.com"},
            "row": {"label": None, "url": "https://google.com"},
        },
        "formula_multipleselect": {
            "blank": [],
            "row": unordered(
                [
                    {"color": "yellow", "id": AnyInt(), "value": "D"},
                    {"color": "orange", "id": AnyInt(), "value": "C"},
                    {"color": "green", "id": AnyInt(), "value": "E"},
                ]
            ),
        },
        "count": {
            "blank": "0",
            "row": "3",
        },
        "rollup": {
            "blank": "0.000",
            "row": "-122.222",
        },
        "duration_rollup_sum": {
            "blank": 0.0,
            "row": 240.0,
        },
        "duration_rollup_avg": {
            "blank": 0.0,
            "row": 120.0,
        },
        "lookup": {
            "blank": [],
            "row": [
                {"id": AnyInt(), "value": "linked_row_1"},
                {"id": AnyInt(), "value": "linked_row_2"},
                {"id": AnyInt(), "value": ""},
            ],
        },
        "uuid": {
            "blank": "00000000-0000-4000-8000-000000000001",
            "row": "00000000-0000-4000-8000-000000000002",
        },
        "autonumber": {
            "blank": 1,
            "row": 2,
        },
        "password": {
            "blank": None,
            "row": True,
        },
        "ai": {
            "blank": None,
            "row": "I'm an AI.",
        },
    }

    looked_up_fields_row = {
        get_field_ref(key): expected_results_by_field_name[key]["row"]
        for key in expected_results_by_field_name.keys()
    }
    looked_up_fields_blank = {
        get_field_ref(key): expected_results_by_field_name[key]["blank"]
        for key in expected_results_by_field_name.keys()
    }

    if user_field_names:
        field_references = [quote(key) for key in expected_results_by_field_name.keys()]
        join_params = (
            f"?{quote(link_row_field.name)}__join={','.join(field_references)}"
            f"&user_field_names=true"
        )
    else:
        field_references = [
            linked_table_model.get_field_object_by_user_field_name(key)["name"]
            for key in expected_results_by_field_name.keys()
        ]
        join_params = f"?field_{link_row_field.id}__join={','.join(field_references)}"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    link_row_ref = (
        link_row_field.name if user_field_names else f"field_{link_row_field.id}"
    )
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"{link_row_ref}": [
                    {
                        "id": linked_blank_row.id,
                        "value": "",
                        **looked_up_fields_blank,
                        "order": AnyStr(),
                    },
                    {
                        "id": linked_row.id,
                        "value": "text",
                        **looked_up_fields_row,
                        "order": AnyStr(),
                    },
                ],
                "id": row.id,
                "order": AnyStr(),
            },
        ],
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_field_to_same_table(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = table
    linked_table_text_field = data_fixture.create_text_field(
        table=table, order=0, name="Text field"
    )
    linked_table_multiselect = data_fixture.create_multiple_select_field(
        table=table, order=0, name="Multiple select"
    )
    select_option_1 = SelectOption.objects.create(
        field=linked_table_multiselect,
        order=1,
        value="Option 1",
        color="blue",
    )
    select_option_2 = SelectOption.objects.create(
        field=linked_table_multiselect,
        order=1,
        value="Option 2",
        color="blue",
    )
    select_option_3 = SelectOption.objects.create(
        field=linked_table_multiselect,
        order=1,
        value="Option 3",
        color="blue",
    )
    linked_table_multiselect.select_options.set(
        [select_option_1, select_option_2, select_option_3]
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    linked_table_row = RowHandler().create_row(
        user,
        linked_table,
        values={
            f"field_{linked_table_text_field.id}": "Text 1",
            f"field_{linked_table_multiselect.id}": [
                select_option_1.id,
                select_option_3.id,
            ],
        },
    )
    table_row = RowHandler().update_row(
        user,
        table,
        linked_table_row,
        values={
            f"field_{link_row_field.id}": [linked_table_row.id],
        },
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f",field_{linked_table_multiselect.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{linked_table_text_field.id}": "Text 1",
                f"field_{linked_table_multiselect.id}": [
                    {
                        "color": "blue",
                        "id": select_option_1.id,
                        "value": "Option 1",
                    },
                    {
                        "color": "blue",
                        "id": select_option_3.id,
                        "value": "Option 3",
                    },
                ],
                f"field_{link_row_field.id}": [
                    {
                        "id": table_row.id,
                        "value": "unnamed row 1",
                        "order": AnyStr(),
                        f"field_{linked_table_text_field.id}": "Text 1",
                        f"field_{linked_table_multiselect.id}": [
                            {
                                "color": "blue",
                                "id": select_option_1.id,
                                "value": "Option 1",
                            },
                            {
                                "color": "blue",
                                "id": select_option_3.id,
                                "value": "Option 3",
                            },
                        ],
                    },
                ],
                "id": table_row.id,
                "order": AnyStr(),
            },
        ],
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_multiple_link_row_fields(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    linked_table_text_field_2 = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field 2"
    )
    linked_table_2 = data_fixture.create_database_table(user=user)
    linked_table_2_text_field = data_fixture.create_text_field(
        table=linked_table_2, order=0, name="Table 2 Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    link_row_field_2 = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table_2
    )
    linked_table_row = RowHandler().create_row(
        user,
        linked_table,
        values={
            f"field_{linked_table_text_field.id}": "Text 1",
            f"field_{linked_table_text_field_2.id}": "Text 2",
        },
    )
    linked_table_2_row = RowHandler().create_row(
        user,
        linked_table_2,
        values={f"field_{linked_table_2_text_field.id}": "Table 2 Text 1"},
    )
    table_row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{link_row_field.id}": [linked_table_row.id],
            f"field_{link_row_field_2.id}": [linked_table_2_row.id],
        },
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f",field_{linked_table_text_field_2.id}"
        f"&field_{link_row_field_2.id}__join=field_{linked_table_2_text_field.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{link_row_field.id}": [
                    {
                        "id": table_row.id,
                        "value": "unnamed row 1",
                        "order": AnyStr(),
                        f"field_{linked_table_text_field.id}": "Text 1",
                        f"field_{linked_table_text_field_2.id}": "Text 2",
                    },
                ],
                f"field_{link_row_field_2.id}": [
                    {
                        "id": table_row.id,
                        "value": "unnamed row 1",
                        "order": AnyStr(),
                        f"field_{linked_table_2_text_field.id}": "Table 2 Text 1",
                    },
                ],
                "id": table_row.id,
                "order": AnyStr(),
            },
        ],
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_multiple_lookups_same_queries(
    data_fixture, api_client, django_assert_max_num_queries
):
    """
    Test that having more rows or multiple target fields to lookup doesn't change
    the number of queries.
    """

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    linked_table_text_field_2 = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field 2"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    linked_table_row = RowHandler().create_row(
        user,
        linked_table,
        values={
            f"field_{linked_table_text_field.id}": "Text 1",
            f"field_{linked_table_text_field_2.id}": "Text 2",
        },
    )
    linked_table_row_2 = RowHandler().create_row(
        user,
        linked_table,
        values={
            f"field_{linked_table_text_field.id}": "Text 1 row 2",
            f"field_{linked_table_text_field_2.id}": "Text 2 row 2",
        },
    )
    table_row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{link_row_field.id}": [linked_table_row.id],
        },
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"

    with CaptureQueriesContext(connection) as query_context:
        api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    # add additional row
    table_row_2 = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{link_row_field.id}": [linked_table_row_2.id],
        },
    )

    # lookup more fields
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f",field_{linked_table_text_field_2.id}"
    )

    with django_assert_max_num_queries(len(query_context.captured_queries)):
        api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")


@pytest.mark.django_db
def test_list_rows_join_lookup_field_multiple_lookups_user_field_names(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    linked_table_text_field_2 = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field 2"
    )
    linked_table_2 = data_fixture.create_database_table(user=user)
    linked_table_2_text_field = data_fixture.create_text_field(
        table=linked_table_2, order=0, name="Table 2 Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    link_row_field_2 = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table_2
    )
    linked_table_row = RowHandler().create_row(
        user,
        linked_table,
        values={
            f"field_{linked_table_text_field.id}": "Text 1",
            f"field_{linked_table_text_field_2.id}": "Text 2",
        },
    )
    linked_table_2_row = RowHandler().create_row(
        user,
        linked_table_2,
        values={f"field_{linked_table_2_text_field.id}": "Table 2 Text 1"},
    )
    table_row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{link_row_field.id}": [linked_table_row.id],
            f"field_{link_row_field_2.id}": [linked_table_2_row.id],
        },
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?{quote(link_row_field.name)}__join={quote(linked_table_text_field.name)}"
        f",{quote(linked_table_text_field_2.name)}"
        f"&{quote(link_row_field_2.name)}__join={quote(linked_table_2_text_field.name)}"
        f"&user_field_names=true"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"{link_row_field.name}": [
                    {
                        "id": table_row.id,
                        "value": "unnamed row 1",
                        "order": AnyStr(),
                        f"{linked_table_text_field.name}": "Text 1",
                        f"{linked_table_text_field_2.name}": "Text 2",
                    },
                ],
                f"{link_row_field_2.name}": [
                    {
                        "id": table_row.id,
                        "order": AnyStr(),
                        "value": "unnamed row 1",
                        f"{linked_table_2_text_field.name}": "Table 2 Text 1",
                    },
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            },
        ],
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_repeated_link_row_param(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f"&field_{link_row_field.id}__join=xxx"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json


@pytest.mark.django_db
def test_list_rows_join_lookup_repeated_lookup_param(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id},field_{linked_table_text_field.id}"
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST, response_json


@pytest.mark.django_db
def test_list_rows_join_lookup_field_with_include_exclude_fields(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    linked_table_text_field = data_fixture.create_text_field(
        table=linked_table, order=0, name="Text field"
    )
    linked_table_2 = data_fixture.create_database_table(user=user)
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    link_row_field_2 = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table_2
    )

    # excluding used link row field will lead to not found
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f"&exclude=field_{link_row_field.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json

    # including without used link row field will lead to not found
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{linked_table_text_field.id}"
        f"&include=field_{link_row_field_2.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json


@pytest.mark.django_db
def test_list_rows_join_lookup_field_doesnt_exist(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    field_outside_linked_table = data_fixture.create_text_field(
        table=table, order=1, name="Text field outside target table"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{field_outside_linked_table.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json == {
        "detail": "The requested field does not exist.",
        "error": "ERROR_FIELD_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_field_doesnt_exist_user_field_names(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    field_outside_linked_table = data_fixture.create_text_field(
        table=table, order=1, name="Name"
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = f"?{quote(link_row_field.name)}__join=DoesNotExist"
    response = api_client.get(
        f"{url}{join_params}&user_field_names=true", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND, response_json
    assert response_json == {
        "detail": "The requested field does not exist.",
        "error": "ERROR_FIELD_DOES_NOT_EXIST",
    }


@pytest.mark.django_db
def test_list_rows_join_lookup_incompatible_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    linked_table = data_fixture.create_database_table(user=user)
    link_row_field_linked_table = data_fixture.create_link_row_field(
        table=linked_table,
        link_row_table=table,
    )
    link_row_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    join_params = (
        f"?field_{link_row_field.id}__join=field_{link_row_field_linked_table.id}"
    )
    response = api_client.get(f"{url}{join_params}", HTTP_AUTHORIZATION=f"JWT {token}")

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json == {
        "detail": "The field type is not compatible with the action.",
        "error": "ERROR_INCOMPATIBLE_FIELD_TYPE",
    }


@pytest.mark.django_db
def test_cannot_create_row_with_data_sync(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_ical_data_sync(table=table)

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_CREATE_ROWS_IN_TABLE"


@pytest.mark.django_db
def test_create_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )
    boolean_field_2 = data_fixture.create_boolean_field(
        table=table, order=3, name="Available", boolean_default=True
    )
    text_field_2 = data_fixture.create_text_field(
        table=table, order=4, name="Description"
    )
    number_field_2 = data_fixture.create_number_field(
        table=table, order=5, name="Stock", number_default=100
    )
    option_field = data_fixture.create_single_select_field(
        table=table, order=5, name="Option"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )
    option_field = FieldHandler().update_field(
        user=user, field=option_field, single_select_default=option_a.id
    )

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, False, True, True, True)

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": 99999}),
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table_2.id}),
        {f"field_{text_field.id}": "Green"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        f"{url}?before=99999",
        {f"field_{text_field.id}": "Green"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": -10,
            f"field_{boolean_field.id}": None,
            f"field_{boolean_field_2.id}": False,
            f"field_{text_field_2.id}": None,
            f"field_{option_field.id}": option_a.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 2
    assert response_json["detail"][f"field_{number_field.id}"][0]["code"] == "min_value"
    assert response_json["detail"][f"field_{boolean_field.id}"][0]["code"] == "null"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        f"{url}",
        "",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_400_BAD_REQUEST, response_json
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"] == {
        "non_field_errors": [
            {
                "code": "invalid",
                "error": "Invalid data. Expected a dictionary, but got str.",
            }
        ]
    }

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1[f"field_{text_field.id}"] == "white"
    assert not response_json_row_1[f"field_{number_field.id}"]
    assert response_json_row_1[f"field_{boolean_field.id}"] is False
    assert response_json_row_1[f"field_{boolean_field_2.id}"] is True
    assert response_json_row_1[f"field_{text_field_2.id}"] is None
    assert response_json_row_1[f"field_{number_field_2.id}"] == "100"
    assert response_json_row_1[f"field_{option_field.id}"] == {
        "id": option_a.id,
        "value": "A",
        "color": "blue",
    }
    assert response_json_row_1["order"] == "1.00000000000000000000"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{number_field.id}": None,
            f"field_{boolean_field.id}": False,
            f"field_{boolean_field_2.id}": False,
            f"field_{text_field_2.id}": "",
            f"field_{number_field_2.id}": 50,
            f"field_{option_field.id}": option_b.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_2 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_2[f"field_{text_field.id}"] == "white"
    assert not response_json_row_2[f"field_{number_field.id}"]
    assert response_json_row_2[f"field_{boolean_field.id}"] is False
    assert response_json_row_2[f"field_{boolean_field_2.id}"] is False
    assert response_json_row_2[f"field_{text_field_2.id}"] == ""
    assert response_json_row_2[f"field_{number_field_2.id}"] == "50"
    assert response_json_row_2[f"field_{option_field.id}"] == {
        "id": option_b.id,
        "value": "B",
        "color": "red",
    }
    assert response_json_row_2["order"] == "2.00000000000000000000"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 120,
            f"field_{boolean_field.id}": True,
            f"field_{boolean_field_2.id}": True,
            f"field_{text_field_2.id}": "Not important",
            f"field_{number_field_2.id}": None,
            f"field_{option_field.id}": option_a.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_3 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_3[f"field_{text_field.id}"] == "Green"
    assert response_json_row_3[f"field_{number_field.id}"] == "120"
    assert response_json_row_3[f"field_{boolean_field.id}"]
    assert response_json_row_3[f"field_{boolean_field_2.id}"]
    assert response_json_row_3[f"field_{text_field_2.id}"] == "Not important"
    assert response_json_row_3[f"field_{number_field_2.id}"] is None
    assert response_json_row_3[f"field_{option_field.id}"] == {
        "id": option_a.id,
        "value": "A",
        "color": "blue",
    }
    assert response_json_row_3["order"] == "3.00000000000000000000"

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "Purple",
            f"field_{number_field.id}": 240,
            f"field_{boolean_field.id}": True,
            f"field_{boolean_field_2.id}": False,
            f"field_{text_field_2.id}": "",
            f"field_{option_field.id}": option_b.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    response_json_row_4 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_4[f"field_{text_field.id}"] == "Purple"
    assert response_json_row_4[f"field_{number_field.id}"] == "240"
    assert response_json_row_4[f"field_{boolean_field.id}"]
    assert response_json_row_4[f"field_{boolean_field_2.id}"] is False
    assert response_json_row_4[f"field_{text_field_2.id}"] == ""
    assert response_json_row_4[f"field_{number_field_2.id}"] == "100"
    assert response_json_row_4[f"field_{option_field.id}"] == {
        "id": option_b.id,
        "value": "B",
        "color": "red",
    }
    assert response_json_row_4["order"] == "4.00000000000000000000"

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        f"{url}?before={response_json_row_3['id']}",
        {
            f"field_{text_field.id}": "Red",
            f"field_{number_field.id}": 480,
            f"field_{boolean_field.id}": False,
            f"field_{boolean_field_2.id}": False,
            f"field_{text_field_2.id}": "",
            f"field_{option_field.id}": option_b.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    response_json_row_5 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_5[f"field_{text_field.id}"] == "Red"
    assert response_json_row_5[f"field_{number_field.id}"] == "480"
    assert not response_json_row_5[f"field_{boolean_field.id}"]
    assert not response_json_row_5[f"field_{boolean_field_2.id}"]
    assert response_json_row_5[f"field_{text_field_2.id}"] == ""
    assert response_json_row_5[f"field_{number_field_2.id}"] == "100"
    assert response_json_row_5[f"field_{option_field.id}"] == {
        "id": option_b.id,
        "value": "B",
        "color": "red",
    }
    assert response_json_row_5["order"] == "2.50000000000000000000"

    model = table.get_model()
    assert model.objects.all().count() == 5
    rows = model.objects.all()

    row_1, row_2, row_5, row_3, row_4 = rows

    assert row_1.id == response_json_row_1["id"]
    assert getattr(row_1, f"field_{text_field.id}") == "white"
    assert getattr(row_1, f"field_{number_field.id}") is None
    assert getattr(row_1, f"field_{boolean_field.id}") is False
    assert getattr(row_1, f"field_{boolean_field_2.id}") is True
    assert getattr(row_1, f"field_{text_field_2.id}") is None
    assert getattr(row_1, f"field_{number_field_2.id}") == 100
    assert getattr(row_1, f"field_{option_field.id}").id == option_a.id

    assert row_2.id == response_json_row_2["id"]
    assert getattr(row_2, f"field_{text_field.id}") == "white"
    assert getattr(row_2, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{boolean_field.id}") is False
    assert getattr(row_2, f"field_{boolean_field_2.id}") is False
    assert getattr(row_2, f"field_{text_field_2.id}") == ""
    assert getattr(row_2, f"field_{number_field_2.id}") == 50
    assert getattr(row_2, f"field_{option_field.id}").id == option_b.id

    assert row_3.id == response_json_row_3["id"]
    assert getattr(row_3, f"field_{text_field.id}") == "Green"
    assert getattr(row_3, f"field_{number_field.id}") == 120
    assert getattr(row_3, f"field_{boolean_field.id}") is True
    assert getattr(row_3, f"field_{boolean_field_2.id}") is True
    assert getattr(row_3, f"field_{text_field_2.id}") == "Not important"
    assert getattr(row_3, f"field_{number_field_2.id}") is None
    assert getattr(row_3, f"field_{option_field.id}").id == option_a.id

    assert row_4.id == response_json_row_4["id"]
    assert getattr(row_4, f"field_{text_field.id}") == "Purple"
    assert getattr(row_4, f"field_{number_field.id}") == 240
    assert getattr(row_4, f"field_{boolean_field.id}") is True
    assert getattr(row_4, f"field_{boolean_field_2.id}") is False
    assert getattr(row_4, f"field_{text_field_2.id}") == ""
    assert getattr(row_4, f"field_{number_field_2.id}") == 100
    assert getattr(row_4, f"field_{option_field.id}").id == option_b.id

    assert row_5.id == response_json_row_5["id"]
    assert getattr(row_5, f"field_{text_field.id}") == "Red"
    assert getattr(row_5, f"field_{number_field.id}") == 480
    assert getattr(row_5, f"field_{boolean_field.id}") is False
    assert getattr(row_5, f"field_{boolean_field_2.id}") is False
    assert getattr(row_5, f"field_{text_field_2.id}") == ""
    assert getattr(row_5, f"field_{number_field_2.id}") == 100
    assert getattr(row_5, f"field_{option_field.id}").id == option_b.id

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    response = api_client.post(
        f"{url}?user_field_names=true",
        {
            f"Color": "Red",
            f"Horsepower": 480,
            f"For Sale": False,
            f"Description": "",
            f"Option": "A",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        # Has gone to the default value when not specified.
        "Available": True,
        "Stock": "100",
        # Fields that are set
        "Color": "Red",
        "Description": "",
        "For sale": False,
        "Horsepower": "480",
        "id": 6,
        "order": "5.00000000000000000000",
        "Option": {"id": option_a.id, "value": "A", "color": "blue"},
    }

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.post(
        f"{url}?user_field_names=true",
        {
            f"INVALID FIELD NAME": "Red",
            f"Horsepower": 480,
            f"For Sale": False,
            f"Description": "",
            f"Option": "A",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        # Has gone to the default value when not specified.
        "Available": True,
        "Color": "white",
        "Stock": "100",
        # Fields that are set
        "Description": "",
        "For sale": False,
        "Horsepower": "480",
        "id": 7,
        "order": "6.00000000000000000000",
        "Option": {"id": option_a.id, "value": "A", "color": "blue"},
    }


@pytest.mark.django_db(transaction=True)
def test_create_row_with_disabled_webhook_events(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.post(
            f"{url}?send_webhook_events=false",
            {f"field_{text_field.id}": "Test 1"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        m.assert_not_called()


@pytest.mark.django_db
def test_create_row_with_read_only_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=True
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {
            f"field_{text_field.id}": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"][f"field_{text_field.id}"][0]["code"] == "read_only"


@pytest.mark.django_db
def test_create_empty_row_for_interesting_fields(api_client, data_fixture):
    """
    Test a common case: create a row with empty values.
    """

    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    jwt_token = data_fixture.generate_token(user)

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id})
        + "?user_field_names=true",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_create_row_with_blank_decimal_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    decimal_field = data_fixture.create_number_field(
        table=table, order=1, name="TestDecimal", number_decimal_places=1
    )

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        {f"field_{decimal_field.id}": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1[f"field_{decimal_field.id}"] is None


@pytest.mark.django_db
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_create_row_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=False
    )

    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.force_create_row"
    ) as mock_force_create_row:
        mock_force_create_row.side_effect = get_deadlock_error()
        response = api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {f"field_{text_field.id}": "Green"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )

    response.json()
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db
def test_get_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, False, True, True)

    model = table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 120,
            f"field_{boolean_field.id}": False,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "Purple",
            f"field_{number_field.id}": 240,
            f"field_{boolean_field.id}": True,
        }
    )

    url = reverse("api:database:rows:item", kwargs={"table_id": 9999, "row_id": 9999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table_2.id, "row_id": row_1.id}
    )
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION="Token abc123")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.get(
        url, format="json", HTTP_AUTHORIZATION=f"Token {wrong_token.key}"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": 99999}
    )
    response = api_client.get(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == row_1.id
    assert response_json[f"field_{text_field.id}"] == "Green"
    assert response_json[f"field_{number_field.id}"] == "120"
    assert response_json[f"field_{boolean_field.id}"] is False

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_2.id}
    )
    response = api_client.get(
        url, format="json", HTTP_AUTHORIZATION=f"Token {token.key}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == row_2.id
    assert response_json[f"field_{text_field.id}"] == "Purple"
    assert response_json[f"field_{number_field.id}"] == "240"
    assert response_json[f"field_{boolean_field.id}"] is True


@pytest.mark.django_db
def test_update_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )
    boolean_field = data_fixture.create_boolean_field(
        table=table, order=2, name="For sale"
    )

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, True, False, True)

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    url = reverse("api:database:rows:item", kwargs={"table_id": 9999, "row_id": 9999})
    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table_2.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": 99999}
    )
    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": -10,
            f"field_{boolean_field.id}": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(response_json["detail"]) == 2
    assert response_json["detail"][f"field_{number_field.id}"][0]["code"] == "min_value"
    assert response_json["detail"][f"field_{boolean_field.id}"][0]["code"] == "null"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        f"{url}",
        "",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"] == {
        "non_field_errors": [
            {
                "code": "invalid",
                "error": "Invalid data. Expected types are: dict, but got str.",
            }
        ]
    }
    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "Green",
            f"field_{number_field.id}": 120,
            f"field_{boolean_field.id}": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1["id"] == row_1.id
    assert response_json_row_1[f"field_{text_field.id}"] == "Green"
    assert response_json_row_1[f"field_{number_field.id}"] == "120"
    assert response_json_row_1[f"field_{boolean_field.id}"] is True

    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "Green"
    assert getattr(row_1, f"field_{number_field.id}") == Decimal("120")
    assert getattr(row_1, f"field_{boolean_field.id}") is True

    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Purple"},
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1[f"field_{text_field.id}"] == "Purple"
    assert response_json_row_1[f"field_{number_field.id}"] == "120"
    assert response_json_row_1[f"field_{boolean_field.id}"] is True
    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "Purple"
    assert getattr(row_1, f"field_{number_field.id}") == Decimal("120")
    assert getattr(row_1, f"field_{boolean_field.id}") is True

    response = api_client.patch(
        url,
        {f"field_{text_field.id}": "Orange"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1[f"field_{text_field.id}"] == "Orange"
    assert response_json_row_1[f"field_{number_field.id}"] == "120"
    assert response_json_row_1[f"field_{boolean_field.id}"] is True
    row_1.refresh_from_db()
    assert getattr(row_1, f"field_{text_field.id}") == "Orange"
    assert getattr(row_1, f"field_{number_field.id}") == 120
    assert getattr(row_1, f"field_{boolean_field.id}") is True

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_2.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "Blue",
            f"field_{number_field.id}": 50,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_2 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_2["id"] == row_2.id
    assert response_json_row_2[f"field_{text_field.id}"] == "Blue"
    assert response_json_row_2[f"field_{number_field.id}"] == "50"
    assert response_json_row_2[f"field_{boolean_field.id}"] is False

    row_2.refresh_from_db()
    assert getattr(row_2, f"field_{text_field.id}") == "Blue"
    assert getattr(row_2, f"field_{number_field.id}") == Decimal("50")
    assert getattr(row_2, f"field_{boolean_field.id}") is False

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_2.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": None,
            f"field_{number_field.id}": None,
            f"field_{boolean_field.id}": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_2 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_2["id"] == row_2.id
    assert response_json_row_2[f"field_{text_field.id}"] is None
    assert response_json_row_2[f"field_{number_field.id}"] is None
    assert response_json_row_2[f"field_{boolean_field.id}"] is False

    row_2.refresh_from_db()
    assert getattr(row_2, f"field_{text_field.id}") is None
    assert getattr(row_2, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{boolean_field.id}") is False

    table_3 = data_fixture.create_database_table(user=user)
    decimal_field = data_fixture.create_number_field(
        table=table_3,
        order=0,
        name="Price",
        number_decimal_places=2,
    )
    model_3 = table_3.get_model()
    row_3 = model_3.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table_3.id, "row_id": row_3.id}
    )
    response = api_client.patch(
        url,
        {f"field_{decimal_field.id}": 10.22},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"field_{decimal_field.id}"] == "10.22"
    assert response_json_row_2[f"field_{number_field.id}"] is None
    assert response_json_row_2[f"field_{boolean_field.id}"] is False

    row_3.refresh_from_db()
    assert getattr(row_3, f"field_{decimal_field.id}") == Decimal("10.22")
    assert getattr(row_2, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{boolean_field.id}") is False

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table_3.id, "row_id": row_3.id}
    )
    response = api_client.patch(
        f"{url}?user_field_names=true",
        {f"Price": 10.01},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json[f"Price"] == "10.01"
    assert "Horsepower" not in response_json
    assert "For sale" not in response_json

    row_3.refresh_from_db()
    assert getattr(row_3, f"field_{decimal_field.id}") == Decimal("10.01")
    assert getattr(row_2, f"field_{number_field.id}") is None
    assert getattr(row_2, f"field_{boolean_field.id}") is False


@pytest.mark.django_db
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_update_row_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=False
    )

    model = table.get_model()
    row_1 = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.force_update_rows"
    ) as mock_force_update_rows:
        mock_force_update_rows.side_effect = get_deadlock_error()
        response = api_client.patch(
            url,
            {
                f"field_{text_field.id}": "Green",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db(transaction=True)
def test_update_row_with_disabled_webhook_events(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )

    model = table.get_model()
    row_1 = model.objects.create()

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.patch(
            f"{url}?send_webhook_events=false",
            {f"field_{text_field.id}": "Test 1"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        m.assert_not_called()


@pytest.mark.django_db
def test_update_row_with_read_only_field(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=True
    )

    model = table.get_model()
    row_1 = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        {
            f"field_{text_field.id}": "Green",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"][f"field_{text_field.id}"][0]["code"] == "read_only"


@pytest.mark.django_db
def test_move_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, True, False, True)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)
    row_3 = handler.create_row(user=user, table=table)

    url = reverse("api:database:rows:move", kwargs={"table_id": 9999, "row_id": 9999})
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table_2.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": 99999}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        f"{url}?before_id=-1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1["id"] == row_1.id
    assert response_json_row_1["order"] == "4.00000000000000000000"

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("4.00000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        f"{url}?before_id={row_3.id}",
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    response_json_row_1 = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json_row_1["id"] == row_1.id
    assert response_json_row_1["order"] == "2.50000000000000000000"

    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    assert row_1.order == Decimal("2.50000000000000000000")
    assert row_2.order == Decimal("2.00000000000000000000")
    assert row_3.order == Decimal("3.00000000000000000000")

    data_fixture.create_text_field(user=user, table=table, name="New Field")
    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.patch(
        f"{url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json_row_1 = response.json()
    assert response_json_row_1 == {
        "New Field": None,
        "id": row_1.id,
        "order": "4.00000000000000000000",
    }

    # Make sure that we receive an error message when calling move row
    # with an before_id != int
    url = reverse("api:database:rows:move", kwargs={"table_id": table.id, "row_id": 1})
    response = api_client.patch(
        f"{url}?before_id=wrong_type",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response_json["detail"]["before_id"][0]["code"] == "invalid"
    assert (
        response_json["detail"]["before_id"][0]["error"]
        == "A valid integer is required."
    )


@pytest.mark.django_db
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_move_row_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = RowHandler()
    row_1 = handler.create_row(user=user, table=table)
    row_2 = handler.create_row(user=user, table=table)

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.move_row"
    ) as mock_move_row:
        mock_move_row.side_effect = get_deadlock_error()
        response = api_client.patch(
            f"{url}?before_id={row_2.id}",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db(transaction=True)
def test_move_row_with_disabled_webhook_events(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
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

    url = reverse(
        "api:database:rows:move", kwargs={"table_id": table.id, "row_id": row_2.id}
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.patch(
            f"{url}?before_id={row_1.id}&send_webhook_events=false",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        m.assert_not_called()


@pytest.mark.django_db
def test_cannot_delete_row_by_id_with_data_sync(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_ical_data_sync(table=table)

    model = table.get_model()
    row_1 = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_ROWS_IN_TABLE"


@pytest.mark.django_db
def test_delete_row_by_id(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table()
    data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    data_fixture.create_number_field(table=table, order=1, name="Horsepower")
    data_fixture.create_boolean_field(table=table, order=2, name="For sale")

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, True, True, False)

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()
    row_3 = model.objects.create()

    url = reverse("api:database:rows:item", kwargs={"table_id": 9999, "row_id": 9999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": 9999}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"Token abc123")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"Token {wrong_token.key}")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table_2.id, "row_id": row_1.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == 204

    assert model.objects.count() == 2
    assert model.objects.all()[0].id == row_2.id

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_2.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
    assert response.status_code == 204
    assert model.objects.count() == 1

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_3.id}
    )
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"Token {token.key}")
    assert response.status_code == 204
    assert model.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_delete_row_by_id_with_disabled_webhook_events(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )

    model = table.get_model()
    row_1 = model.objects.create()

    data_fixture.create_table_webhook(
        table=table,
        user=user,
        request_method="POST",
        url="http://localhost",
        events=[],
    )

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as m:
        response = api_client.delete(
            f"{url}?send_webhook_events=false",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        m.assert_not_called()


@pytest.mark.django_db
@override_settings(BASEROW_DEADLOCK_INITIAL_BACKOFF=0.01)
@override_settings(BASEROW_DEADLOCK_MAX_RETRIES=1)
def test_delete_row_deadlock(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="", read_only=False
    )

    model = table.get_model()
    row_1 = model.objects.create()

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    with patch(
        "baserow.contrib.database.rows.handler.RowHandler.delete_row"
    ) as mock_delete_row:
        mock_delete_row.side_effect = get_deadlock_error()
        response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")

    assert response.status_code == HTTP_409_CONFLICT
    assert response.json()["error"] == "ERROR_DATABASE_DEADLOCK"


@pytest.mark.django_db
def test_list_rows_with_attribute_names(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    table_to_link_with = data_fixture.create_database_table(
        user=user, database=table.database
    )
    data_fixture.create_text_field(
        primary=True,
        name="Primary",
        table=table_to_link_with,
    )
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)
    field_2 = data_fixture.create_number_field(name="Price,", table=table)
    field_3 = data_fixture.create_boolean_field(name='"Name, 2"', table=table)
    link_field = FieldHandler().create_field(
        user, table, "link_row", link_row_table=table_to_link_with, name="Link"
    )
    password_field = data_fixture.create_password_field(name="Password", table=table)

    model = table.get_model()
    row_1 = model.objects.create(
        **{
            f"field_{field_1.id}": "name 1",
            f"field_{field_2.id}": 2,
            f"field_{field_3.id}": False,
        }
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            '"Name, 2"': False,
            "Name": "name 1",
            "Price,": "2",
            "id": 1,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        }
    ]

    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row_1.id}
    )
    response = api_client.get(
        f"{url}?user_field_names=true",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "id": 1,
        "Name": "name 1",
        '"Name, 2"': False,
        "order": "1.00000000000000000000",
        "Price,": "2",
        "Link": [],
        "Password": None,
    }

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f'{url}?user_field_names=true&include="\\"Name, 2\\""',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            '"Name, 2"': False,
            "id": 1,
            "order": "1.00000000000000000000",
        }
    ]

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f'{url}?user_field_names=true&exclude="\\"Name, 2\\""',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            "Name": "name 1",
            "Price,": "2",
            "id": 1,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        }
    ]

    model.objects.create(
        **{
            f"field_{field_1.id}": "name 2",
            f"field_{field_2.id}": 1,
            f"field_{field_3.id}": True,
        }
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=true&order_by={password_field.name}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response_json["detail"]
        == "It is not possible to order by Password using sort type default because "
        "the field type password does not support it."
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=true&order_by=Name",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            '"Name, 2"': False,
            "Name": "name 1",
            "Price,": "2",
            "id": 1,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        },
        {
            '"Name, 2"': True,
            "Name": "name 2",
            "Price,": "1",
            "id": 2,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        },
    ]

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f'{url}?user_field_names=true&order_by="-\\"Name, 2\\""',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            '"Name, 2"': True,
            "Name": "name 2",
            "Price,": "1",
            "id": 2,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        },
        {
            '"Name, 2"': False,
            "Name": "name 1",
            "Price,": "2",
            "id": 1,
            "order": "1.00000000000000000000",
            "Link": [],
            "Password": None,
        },
    ]

    # make sure that when user_field_names is not set
    # that a correct error is presented when still using
    # a field names in order_by
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by={field_1.name}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"
    assert (
        response_json["detail"]
        == f"The field {field_1.name} was not found in the table."
    )

    # make sure that when user_field_names is false and we provide
    # a field_id string that we get a result.
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=false&order_by=field_{field_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["results"] == [
        {
            "id": 1,
            "order": "1.00000000000000000000",
            f"field_{field_1.id}": "name 1",
            f"field_{field_3.id}": False,
            f"field_{field_2.id}": "2",
            f"field_{link_field.id}": [],
            f"field_{password_field.id}": None,
        },
        {
            "id": 2,
            "order": "1.00000000000000000000",
            f"field_{field_1.id}": "name 2",
            f"field_{field_3.id}": True,
            f"field_{field_2.id}": "1",
            f"field_{link_field.id}": [],
            f"field_{password_field.id}": None,
        },
    ]

    # make sure that when user_field_names is true and we provide
    # a field_id string that we get an error.
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=true&order_by=field_{field_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"
    assert (
        response_json["detail"]
        == f"The field field_{field_1.id} was not found in the table."
    )


@pytest.mark.django_db
def test_list_rows_returns_https_next_url(api_client, data_fixture, settings):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(name="Name", table=table, primary=True)

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{field_1.id}": "name 1",
        }
    )
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["next"] is None

    for i in range(settings.ROW_PAGE_SIZE_LIMIT + 1):
        model.objects.create(
            **{
                f"field_{field_1.id}": f"name {i}",
            }
        )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert (
        response_json["next"] == "http://testserver/api/database/rows/table/"
        f"{table.id}/?page=2"
    )

    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        HTTP_X_FORWARDED_PROTO="https",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert (
        response_json["next"] == "https://testserver:80/api/database/rows/table/"
        f"{table.id}/?page=2"
    )


@pytest.mark.django_db
def test_list_row_names(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(name="Name", table=table, primary=True)

    # A table for another user
    table_off = data_fixture.create_database_table()

    # A table in the same database
    table_2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="Name", table=table_2, primary=True)

    # A table in another database
    table_3 = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(name="Name", table=table_3, primary=True)

    token = TokenHandler().create_token(user, table.database.workspace, "Good")
    wrong_token = TokenHandler().create_token(user, table.database.workspace, "Wrong")
    TokenHandler().update_token_permissions(user, wrong_token, True, False, True, True)

    model = table.get_model(attribute_names=True)
    model.objects.create(name="Alpha")
    model.objects.create(name="Beta")
    model.objects.create(name="Gamma")
    model.objects.create(name="Omega")

    model_2 = table_2.get_model(attribute_names=True)
    model_2.objects.create(name="Monday")
    model_2.objects.create(name="Tuesday")

    model_3 = table_3.get_model(attribute_names=True)
    model_3.objects.create(name="January")

    url = reverse("api:database:rows:names")
    response = api_client.get(
        f"{url}?table__99999=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3&table__99999=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        f"{url}?table__{table_off.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION="Token abc123",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_TOKEN_DOES_NOT_EXIST"

    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"Token {wrong_token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"

    user.is_active = False
    user.save()
    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_USER_NOT_ACTIVE"
    user.is_active = True
    user.save()

    response = api_client.get(
        f"{url}?tabble__{table.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert (
        response.json()["detail"]
        == 'Only table Id prefixed by "table__" are allowed as parameter.'
    )

    response = api_client.get(
        f"{url}?table__12i=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json()["detail"] == 'Failed to parse table id in "table__12i".'

    response = api_client.get(
        f"{url}?table__23=1p,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert (
        response.json()["detail"]
        == 'Failed to parse row ids in "1p,2,3" for "table__23" parameter.'
    )

    response = api_client.get(
        f"{url}?table__{table.id}=1",
        format="json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert response.status_code == HTTP_200_OK

    # One query one table
    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {str(table.id): {"1": "Alpha", "2": "Beta", "3": "Gamma"}}

    # 2 tables, one database
    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3&table__{table_2.id}=1,2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {
        str(table.id): {"1": "Alpha", "2": "Beta", "3": "Gamma"},
        str(table_2.id): {"1": "Monday", "2": "Tuesday"},
    }

    # Two tables, two databases
    response = api_client.get(
        f"{url}?table__{table.id}=1,2,3&table__{table_3.id}=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_row_adjacent(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(name="table", user=user)
    field = data_fixture.create_text_field(name="some name", table=table)

    [row_1, row_2, row_3] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "some value"},
                {f"field_{field.id}": "some value"},
                {f"field_{field.id}": "some value"},
            ],
        )
        .created_rows
    )

    # Get the next row
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row_2.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"user_field_names": True},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == row_3.id
    assert field.name in response_json

    # Get the previous row
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row_2.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"previous": True},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == row_1.id


@pytest.mark.django_db
def test_get_row_adjacent_view_id_provided(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(name="table", user=user)
    view = data_fixture.create_grid_view(name="view", user=user, table=table)
    field = data_fixture.create_text_field(name="field", table=table)

    data_fixture.create_view_sort(user, field=field, view=view)
    data_fixture.create_view_filter(
        user, field=field, view=view, type="contains", value="a"
    )

    [row_1, row_2, row_3] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "ab"},
                {f"field_{field.id}": "b"},
                {f"field_{field.id}": "a"},
            ],
        )
        .created_rows
    )

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row_3.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": view.id},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == row_1.id


@pytest.mark.django_db
def test_get_row_adjacent_view_id_no_adjacent_row(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(name="table", user=user)
    field = data_fixture.create_text_field(name="field", table=table)

    [row_1, row_2, row_3] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "a"},
                {f"field_{field.id}": "b"},
                {f"field_{field.id}": "c"},
            ],
        )
        .created_rows
    )

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row_3.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_get_row_adjacent_view_invalid_requests(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    user_2, jwt_token_2 = data_fixture.create_user_and_token(
        email="test2@test.nl", password="password", first_name="Test2"
    )
    table = data_fixture.create_database_table(name="table", user=user)
    table_unrelated = data_fixture.create_database_table(
        name="table unrelated", user=user
    )
    view_unrelated = data_fixture.create_grid_view(table=table_unrelated)

    row = RowHandler().create_row(user, table, {})

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token_2}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": 999999, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.data["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        data={"view_id": 999999},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.data["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": 99999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.data["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        data={"view_id": view_unrelated.id},
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.data["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_get_row_adjacent_search(api_client, data_fixture, search_mode):
    user, jwt_token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(name="table", user=user)
    field = data_fixture.create_text_field(name="field", table=table)

    [row_1, row_2, row_3] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "a"},
                {f"field_{field.id}": "ab"},
                {f"field_{field.id}": "c"},
            ],
        )
        .created_rows
    )

    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row_2.id},
        ),
        data={"search": "a", "search_mode": search_mode},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT, response.json()


@pytest.mark.django_db
@pytest.mark.row_history
def test_list_row_history_for_different_rows(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )

    row_handler = RowHandler()

    row_one = row_handler.create_row(user, table, {name_field.id: "Original 1"})
    row_two = row_handler.create_row(user, table, {name_field.id: "Original 2"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {
                    "id": row_one.id,
                    f"field_{name_field.id}": "New 1",
                    f"field_{number_field.id}": "1.00",
                },
                {
                    "id": row_two.id,
                    f"field_{name_field.id}": "New 2",
                    f"field_{number_field.id}": None,
                },
            ],
        )

    with freeze_time("2021-01-01 12:01"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [{"id": row_one.id, f"field_{name_field.id}": "New 1.1"}],
        )

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row_one.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:01:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1",
                },
                "after": {
                    f"field_{name_field.id}": "New 1.1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                    f"field_{number_field.id}": None,
                },
                "after": {
                    f"field_{name_field.id}": "New 1",
                    f"field_{number_field.id}": "1.00",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                    f"field_{number_field.id}": {
                        "id": number_field.id,
                        "type": "number",
                        "number_decimal_places": 2,
                        "number_negative": False,
                        "number_prefix": "",
                        "number_separator": "",
                        "number_suffix": "",
                    },
                },
            },
        ],
    }

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row_two.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 2",
                },
                "after": {
                    f"field_{name_field.id}": "New 2",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
        ],
    }


@pytest.mark.django_db
@pytest.mark.row_history
def test_list_row_history_for_different_fields(data_fixture, api_client):
    workspace = data_fixture.create_workspace()
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    user, jwt_token = data_fixture.create_user_and_token(workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    number_field = data_fixture.create_number_field(
        table=table, name="Number", number_decimal_places=2
    )
    email_field = data_fixture.create_email_field(table=table, name="Email")
    url_field = data_fixture.create_url_field(table=table, name="URL")
    rating_field = data_fixture.create_rating_field(
        table=table, user=user, name="Rating", max_value=5
    )
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    phone_field = data_fixture.create_phone_number_field(table=table, name="Phone")
    date_field = data_fixture.create_date_field(
        table=table, date_include_time=False, date_format="ISO", name="Date"
    )
    datetime_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO", name="Date"
    )
    file_field = data_fixture.create_file_field(table=table, name="File")
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file1.uploaded_at = datetime(2021, 1, 1, 12, 30, tzinfo=timezone.utc)
    file1.save()
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )
    single_select_field = data_fixture.create_single_select_field(
        table=table, name="Single select"
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="B", color="red"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="Multiple select"
    )
    multi_option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue"
    )
    multi_option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red"
    )
    multiple_select_field.select_options.set([multi_option_a, multi_option_b])
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        table=table, name="Collaborators", notify_user_when_added=False
    )
    linkrow_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    table2_model = table2.get_model()
    table2_row1 = table2_model.objects.create()
    table2_row2 = table2_model.objects.create()

    row_handler = RowHandler()

    row_one = row_handler.create_row(
        user,
        table,
        {
            name_field.id: "Original 1",
            number_field.id: "0.00",
            email_field.id: "test@example.com",
            url_field.id: "http://baserow.io",
            rating_field.id: 3,
            boolean_field.id: False,
            phone_field.id: "123456789",
            date_field.id: "2023-06-06",
            datetime_field.id: "2023-06-06T12:00",
            file_field.id: [{"name": file1.name, "visible_name": "file 1"}],
            single_select_field.id: option_a,
            multiple_select_field.id: [multi_option_a.id],
            collaborator_field.id: [{"id": user2.id}, {"id": user3.id}],
            linkrow_field.id: [table2_row1.id],
        },
    )

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {
                    "id": row_one.id,
                    f"field_{name_field.id}": "New 1",
                    f"field_{number_field.id}": "1.00",
                    f"field_{email_field.id}": "test2@example.com",
                    f"field_{url_field.id}": "https://baserow.io",
                    f"field_{rating_field.id}": 5,
                    f"field_{boolean_field.id}": True,
                    f"field_{phone_field.id}": "123456790",
                    f"field_{date_field.id}": "2023-06-07",
                    f"field_{datetime_field.id}": "2023-06-06T13:00",
                    f"field_{file_field.id}": [
                        {"name": file1.name, "visible_name": "file 1"},
                        {"name": file2.name, "visible_name": "file 2"},
                    ],
                    f"field_{single_select_field.id}": option_b.id,
                    f"field_{multiple_select_field.id}": [
                        multi_option_a.id,
                        multi_option_b.id,
                    ],
                    f"field_{collaborator_field.id}": [{"id": user2.id}],
                    f"field_{linkrow_field.id}": [table2_row1.id, table2_row2.id],
                },
            ],
        )

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row_one.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    expected_output = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                    f"field_{number_field.id}": "0.00",
                    f"field_{email_field.id}": "test@example.com",
                    f"field_{url_field.id}": "http://baserow.io",
                    f"field_{rating_field.id}": 3,
                    f"field_{boolean_field.id}": False,
                    f"field_{phone_field.id}": "123456789",
                    f"field_{date_field.id}": "2023-06-06",
                    f"field_{datetime_field.id}": "2023-06-06 12:00:00+00:00",
                    f"field_{file_field.id}": [
                        {
                            "name": file1.name,
                            "visible_name": "file 1",
                            "image_height": None,
                            "image_width": None,
                            "is_image": True,
                            "mime_type": "text/plain",
                            "size": 100,
                            "uploaded_at": "2021-01-01T12:30:00+00:00",
                        },
                    ],
                    f"field_{single_select_field.id}": option_a.id,
                    f"field_{multiple_select_field.id}": [multi_option_a.id],
                    f"field_{collaborator_field.id}": [user2.id, user3.id],
                    f"field_{linkrow_field.id}": [table2_row1.id],
                },
                "after": {
                    f"field_{name_field.id}": "New 1",
                    f"field_{number_field.id}": "1.00",
                    f"field_{email_field.id}": "test2@example.com",
                    f"field_{url_field.id}": "https://baserow.io",
                    f"field_{rating_field.id}": 5,
                    f"field_{boolean_field.id}": True,
                    f"field_{phone_field.id}": "123456790",
                    f"field_{date_field.id}": "2023-06-07",
                    f"field_{datetime_field.id}": "2023-06-06 13:00:00+00:00",
                    f"field_{file_field.id}": [
                        {
                            "image_height": None,
                            "image_width": None,
                            "is_image": True,
                            "mime_type": "text/plain",
                            "name": AnyStr(),
                            "size": 100,
                            "uploaded_at": AnyStr(),
                            "visible_name": "file 1",
                        },
                        {
                            "image_height": None,
                            "image_width": None,
                            "is_image": True,
                            "mime_type": "text/plain",
                            "name": AnyStr(),
                            "size": 100,
                            "uploaded_at": AnyStr(),
                            "visible_name": "file 2",
                        },
                    ],
                    f"field_{single_select_field.id}": option_b.id,
                    f"field_{multiple_select_field.id}": [
                        multi_option_a.id,
                        multi_option_b.id,
                    ],
                    f"field_{collaborator_field.id}": [
                        user2.id,
                    ],
                    f"field_{linkrow_field.id}": [table2_row1.id, table2_row2.id],
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                    f"field_{number_field.id}": {
                        "id": number_field.id,
                        "number_decimal_places": 2,
                        "number_negative": False,
                        "number_prefix": "",
                        "number_separator": "",
                        "number_suffix": "",
                        "type": "number",
                    },
                    f"field_{email_field.id}": {
                        "id": email_field.id,
                        "type": "email",
                    },
                    f"field_{url_field.id}": {
                        "id": url_field.id,
                        "type": "url",
                    },
                    f"field_{rating_field.id}": {
                        "id": rating_field.id,
                        "type": "rating",
                    },
                    f"field_{boolean_field.id}": {
                        "id": boolean_field.id,
                        "type": "boolean",
                    },
                    f"field_{phone_field.id}": {
                        "id": phone_field.id,
                        "type": "phone_number",
                    },
                    f"field_{date_field.id}": {
                        "id": date_field.id,
                        "type": "date",
                        "date_force_timezone": None,
                        "date_format": "ISO",
                        "date_include_time": False,
                        "date_time_format": "24",
                        "date_show_tzinfo": False,
                    },
                    f"field_{datetime_field.id}": {
                        "id": datetime_field.id,
                        "type": "date",
                        "date_force_timezone": None,
                        "date_format": "ISO",
                        "date_include_time": True,
                        "date_time_format": "24",
                        "date_show_tzinfo": False,
                    },
                    f"field_{file_field.id}": {
                        "id": file_field.id,
                        "type": "file",
                    },
                    f"field_{single_select_field.id}": {
                        "id": single_select_field.id,
                        "select_options": {
                            f"{option_a.id}": {
                                "color": option_a.color,
                                "id": option_a.id,
                                "value": option_a.value,
                            },
                            f"{option_b.id}": {
                                "color": option_b.color,
                                "id": option_b.id,
                                "value": option_b.value,
                            },
                        },
                        "type": "single_select",
                    },
                    f"field_{multiple_select_field.id}": {
                        "id": multiple_select_field.id,
                        "select_options": {
                            f"{multi_option_a.id}": {
                                "color": multi_option_a.color,
                                "id": multi_option_a.id,
                                "value": multi_option_a.value,
                            },
                            f"{multi_option_b.id}": {
                                "color": multi_option_b.color,
                                "id": multi_option_b.id,
                                "value": multi_option_b.value,
                            },
                        },
                        "type": "multiple_select",
                    },
                    f"field_{collaborator_field.id}": {
                        "id": collaborator_field.id,
                        "type": "multiple_collaborators",
                        "collaborators": {
                            f"{user2.id}": {"id": user2.id, "name": user2.first_name},
                            f"{user3.id}": {"id": user3.id, "name": user3.first_name},
                        },
                    },
                    f"field_{linkrow_field.id}": {
                        "id": linkrow_field.id,
                        "type": "link_row",
                        "linked_rows": {
                            f"{table2_row1.id}": {
                                "value": f"unnamed row {table2_row1.id}"
                            },
                            f"{table2_row2.id}": {
                                "value": f"unnamed row {table2_row2.id}"
                            },
                        },
                        "linked_table_id": linkrow_field.link_row_table_id,
                        "linked_field_id": linkrow_field.link_row_related_field_id,
                        "primary_value": "unnamed row 1",
                    },
                },
            },
        ],
    }
    assert response.json() == expected_output


@pytest.mark.django_db
@pytest.mark.row_history
def test_undo_redo_create_new_entries_in_row_history(data_fixture, api_client):
    session_id = "session_id"
    user, jwt_token = data_fixture.create_user_and_token(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(table=table, name="Name")

    row_handler = RowHandler()

    row = row_handler.create_row(user, table, {name_field.id: "Original 1"})

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row.id, f"field_{name_field.id}": "New 1"},
            ],
        )

    # undo
    with freeze_time("2021-01-01 12:01"):
        actions = ActionHandler.undo(
            user, [UpdateRowsActionType.scope(table.id)], session_id
        )
        assert_undo_redo_actions_are_valid(actions, [UpdateRowsActionType])

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "UNDO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:01:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1",
                },
                "after": {
                    f"field_{name_field.id}": "Original 1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                },
                "after": {
                    f"field_{name_field.id}": "New 1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                },
            },
        ],
    }

    # redo
    with freeze_time("2021-01-01 12:02"):
        actions = ActionHandler.redo(
            user, [UpdateRowsActionType.scope(table.id)], session_id
        )
        assert_undo_redo_actions_are_valid(actions, [UpdateRowsActionType])

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "REDO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:02:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                },
                "after": {
                    f"field_{name_field.id}": "New 1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "UNDO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:01:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1",
                },
                "after": {
                    f"field_{name_field.id}": "Original 1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2021-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                },
                "after": {
                    f"field_{name_field.id}": "New 1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    },
                },
            },
        ],
    }


@pytest.mark.django_db
@pytest.mark.row_history
def test_list_row_history_endpoint_handle_errors_correctly(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token()
    _, other_token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    row = RowHandler().create_row(user, table, {name_field.id: "Original 1"})

    with freeze_time("2021-01-01 12:01"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [{"id": row.id, f"field_{name_field.id}": "New 1.1"}],
        )

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": 9999, "row_id": row.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.row_history
@override_settings(ROW_PAGE_SIZE_LIMIT=10)
def test_list_row_history_endpoint_is_paginated(data_fixture, api_client):
    user, jwt_token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(
        name="Test", user=user, database=database
    )
    name_field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    row = RowHandler().create_row(user, table, {name_field.id: "Original 1"})

    for i in range(5):
        timestamp = datetime(2023, 1, 1, 12) + timedelta(minutes=i)
        with freeze_time(timestamp):
            action_type_registry.get_by_type(UpdateRowsActionType).do(
                user,
                table,
                [{"id": row.id, f"field_{name_field.id}": f"New 1.{i}"}],
            )

    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + "?limit=2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 5,
        "next": f"http://testserver/api/database/rows/table/{table.id}/{row.id}/history/?limit=2&offset=2",
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2023-01-01T12:04:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1.3",
                },
                "after": {
                    f"field_{name_field.id}": "New 1.4",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2023-01-01T12:03:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1.2",
                },
                "after": {
                    f"field_{name_field.id}": "New 1.3",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
        ],
    }

    # Use offset
    response = api_client.get(
        reverse(
            "api:database:rows:history",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + "?offset=3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 5,
        "next": None,
        "previous": f"http://testserver/api/database/rows/table/{table.id}/{row.id}/history/?limit=10",
        "results": [
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2023-01-01T12:01:00Z",
                "before": {
                    f"field_{name_field.id}": "New 1.0",
                },
                "after": {
                    f"field_{name_field.id}": "New 1.1",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
            {
                "id": AnyInt(),
                "action_type": "update_rows",
                "action_command_type": "DO",
                "user": {
                    "id": user.id,
                    "name": user.first_name,
                },
                "timestamp": "2023-01-01T12:00:00Z",
                "before": {
                    f"field_{name_field.id}": "Original 1",
                },
                "after": {
                    f"field_{name_field.id}": "New 1.0",
                },
                "fields_metadata": {
                    f"field_{name_field.id}": {
                        "id": name_field.id,
                        "type": "text",
                    }
                },
            },
        ],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_params", [{"include": "Name"}, {"exclude": "Org,Active"}]
)
def test_list_rows_can_combine_view_id_with_include_exclude(
    data_fixture, api_client, query_params
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, name="Name")
    org_field = data_fixture.create_text_field(table=table, name="Org")
    active_field = data_fixture.create_boolean_field(table=table, name="Active")
    RowHandler().create_rows(
        user,
        table,
        [
            {
                name_field.db_column: "Paul",
                org_field.db_column: "A",
                active_field.db_column: True,
            },
            {
                name_field.db_column: "John",
                org_field.db_column: "B",
                active_field.db_column: False,
            },
            {
                name_field.db_column: "Jack",
                org_field.db_column: "B",
                active_field.db_column: True,
            },
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    data_fixture.create_view_group_by(user, view=view, field=org_field)
    data_fixture.create_view_sort(user, view=view, field=active_field, order="ASC")
    data_fixture.create_view_filter(
        user, field=active_field, view=view, type="boolean", value="1"
    )

    rsp = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        data={"view_id": view.id, "user_field_names": True, **query_params},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json()["results"] == [
        {"id": AnyInt(), "order": AnyStr(), "Name": "Paul"},
        {"id": AnyInt(), "order": AnyStr(), "Name": "Jack"},
    ]


def number_formula_field_factory(data_fixture, table, user, **kwargs):
    return data_fixture.create_formula_field(
        table=table,
        name="target",
        number_decimal_places=1,
        formula="row_id()",
        **kwargs,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "primary_field_factory",
    [
        uuid_field_factory,
        autonumber_field_factory,
        number_formula_field_factory,
    ],
)
def test_link_row_field_validate_input_data_for_read_only_primary_fields(
    data_fixture, api_client, primary_field_factory
):
    # providing an incompatible value to a read-only field should be handled correctly.
    # This fixes the issue #3347

    user, jwt_token = data_fixture.create_user_and_token()
    table_b = data_fixture.create_database_table(user=user)
    pk_field = primary_field_factory(data_fixture, table_b, user, primary=True)
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(
        user=user, table_b=table_b
    )

    (row_b1,) = RowHandler().create_rows(user, table_b, [{}]).created_rows
    row_b1_pk = str(getattr(row_b1, pk_field.db_column))
    # using a valid value as reference to the row should work
    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table_a.id}),
        data={"items": [{link_a_to_b.db_column: [row_b1_pk]}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_items = response.json()["items"][0][link_a_to_b.db_column]
    assert response_items[0]["id"] == row_b1.id

    # using an invalid value as reference to the row should fail with a 400
    response = api_client.post(
        reverse("api:database:rows:batch", kwargs={"table_id": table_a.id}),
        data={"items": [{link_a_to_b.db_column: ["X"]}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_single_field_does_not_affect_others(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table, user, row, blank_row, context = setup_interesting_test_table(
        data_fixture, user=user
    )

    values = {
        "text": "text updated",
        "long_text": "long_text updated",
        "negative_decimal": "-10.2",
        "rating": 2,
        "boolean": False,
        "datetime_us": "2025-05-14T13:37:00Z",
        "date_us": "2025-05-14",
        "duration_hm": 0,
        "file": [],
        "single_select": None,
        "multiple_select": [],
        "multiple_collaborators": [],
        "phone_number": "+44876543210",
    }
    field_ids = context["name_to_field_id"]
    url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    initial_data = response.json()

    original_values = {
        field_id: initial_data.get(f"field_{field_id}")
        for field_id in field_ids.values()
    }

    for field_name, new_value in values.items():
        field_id = field_ids[field_name]
        response = api_client.patch(
            url,
            {f"field_{field_id}": new_value},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        )
        assert response.status_code == HTTP_200_OK
        updated_data = response.json()

        for check_field_name in values.keys():
            check_field_id = field_ids[check_field_name]
            old_val = original_values[check_field_id]
            key = f"field_{check_field_id}"
            if check_field_id == field_id:
                assert updated_data[key] == new_value
            else:
                assert updated_data[key] == old_val

        # Update original_values for next iteration
        original_values[field_id] = updated_data[f"field_{field_id}"]
