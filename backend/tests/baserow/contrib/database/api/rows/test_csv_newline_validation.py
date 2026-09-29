from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_rows_order_by_with_newline_returns_400(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?order_by=field_1%0Afield_2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"


@pytest.mark.django_db
@pytest.mark.parametrize("param", ["include", "exclude"])
def test_list_rows_include_exclude_with_newline_returns_400(
    param, api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?user_field_names=true&{param}=a%0Ab",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
