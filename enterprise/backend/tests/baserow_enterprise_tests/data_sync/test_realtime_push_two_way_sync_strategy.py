from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from starlette.status import HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_create_two_way_data_sync_strategy_without_enterprise_license(
    enterprise_data_fixture, create_postgresql_test_table, api_client
):
    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id", "text_col"],
            "two_way_sync": True,
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_two_way_data_sync_strategy_without_enterprise_license(
    enterprise_data_fixture, create_postgresql_test_table, api_client
):
    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id", "text_col"],
            "two_way_sync": False,
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    data_sync_id = response_json["data_sync"]["id"]

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync_id})
    response = api_client.patch(
        url,
        {
            "two_way_sync": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response_json["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
