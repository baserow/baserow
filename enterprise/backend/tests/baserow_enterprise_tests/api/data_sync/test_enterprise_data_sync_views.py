from datetime import time

from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_existing_periodic_data_sync_interval(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    response = api_client.get(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "interval": "DAILY",
        "when": "12:10:01.000001",
        "automatically_deactivated": False,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_not_existing_periodic_data_sync_interval(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    response = api_client.get(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "interval": "MANUAL",
        "when": None,
        "automatically_deactivated": False,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_periodic_data_sync_interval_without_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    response = api_client.get(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_periodic_data_sync(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    response = api_client.patch(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        {"interval": "HOURLY", "when": "12:10:01.000001"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "interval": "HOURLY",
        "when": "12:10:01.000001",
        "automatically_deactivated": False,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_without_license(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    response = api_client.patch(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        {"interval": "HOURLY", "when": "12:10:01.000001"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_automatically_deactivated_false(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.automatically_deactivated = True

    response = api_client.patch(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        {
            "interval": "HOURLY",
            "when": "12:10:01.000001",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["automatically_deactivated"] is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_audit_log_created(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    response = api_client.patch(
        reverse(
            f"api:enterprise:data_sync:periodic_interval",
            kwargs={"data_sync_id": data_sync.id},
        ),
        {"interval": "HOURLY", "when": "12:10:01.000001"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.get(
        action_type="update_periodic_data_sync_interval"
    )
    assert audit_log_entry.action_params == {
        "when": "12:10:01",
        "interval": "HOURLY",
        "table_id": data_sync.table_id,
        "table_name": data_sync.table.name,
        "database_id": data_sync.table.database_id,
        "data_sync_id": data_sync.id,
        "database_name": data_sync.table.database.name,
    }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_create_data_sync_with_two_way_sync_supported_type(
    enterprise_data_fixture, api_client, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id"],
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
    assert response.status_code == HTTP_200_OK

    data_sync = DataSync.objects.get(id=response.json()["data_sync"]["id"])
    assert data_sync.two_way_sync is True
    assert response.json()["data_sync"]["two_way_sync"] is True


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_data_sync_enable_two_way_sync_supported_type(
    enterprise_data_fixture, api_client, create_postgresql_test_table, synced_roles
):
    # @TODO remove this.
    enterprise_data_fixture.delete_all_licenses()

    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "two_way_sync": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["two_way_sync"] is True

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "postgresql_host": default_database["HOST"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    # Should remain True, if not provided in the body payload.
    assert response.json()["two_way_sync"] is True


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_can_create_row_with_two_way_data_sync(
    enterprise_data_fixture, api_client, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

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
    table_id = response.json()["id"]

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table_id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_can_delete_row_with_two_way_data_sync(
    enterprise_data_fixture, api_client, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

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
    table_id = response.json()["id"]
    data_sync_id = response_json["data_sync"]["id"]

    api_client.post(
        reverse(
            "api:database:data_sync:sync_table", kwargs={"data_sync_id": data_sync_id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    url = reverse("api:database:rows:item", kwargs={"table_id": table_id, "row_id": 1})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
