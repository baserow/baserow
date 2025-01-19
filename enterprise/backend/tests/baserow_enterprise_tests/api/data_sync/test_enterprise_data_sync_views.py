from datetime import time

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_402_PAYMENT_REQUIRED

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
