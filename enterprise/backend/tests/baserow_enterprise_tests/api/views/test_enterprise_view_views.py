from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
def test_create_restricted_grid_view_without_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_restricted_grid_view_with_license(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["ownership_type"] == "restricted"
