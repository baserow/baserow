from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

import pytest
import responses
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import (
    DataSync,
    DataSyncSyncedProperty,
    SyncDataSyncTableJob,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import WorkspaceUser

ICAL_FEED_WITH_ONE_ITEMS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ical.marudot.com//iCal Event Maker
X-WR-CALNAME:Test feed
NAME:Test feed
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:Europe/Berlin
LAST-MODIFIED:20231222T233358Z
TZURL:https://www.tzurl.org/zoneinfo-outlook/Europe/Berlin
X-LIC-LOCATION:Europe/Berlin
BEGIN:DAYLIGHT
TZNAME:CEST
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZNAME:CET
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
DTSTAMP:20240901T195538Z
UID:1725220374375-34056@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240901T100000
DTEND;TZID=Europe/Berlin:20240901T110000
SUMMARY:Test event 0
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
END:VCALENDAR"""


@pytest.mark.django_db
def test_create_data_sync_no_permissions(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application()

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_create_data_sync_invalid_type(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["type"][0]["code"] == "invalid_choice"


@pytest.mark.django_db
def test_create_data_sync_wrong_properties(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["TEST"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_PROPERTY_NOT_FOUND"
    assert "TEST" in response_json["detail"]


@pytest.mark.django_db
def test_create_data_sync_invalid_polymorphic_property(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid"],
            "ical_url": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_data_sync_without_data(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "type": "ical_calendar",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["synced_properties"][0]["code"] == "required"
    assert response_json["detail"]["table_name"][0]["code"] == "required"
    assert response_json["detail"]["ical_url"][0]["code"] == "required"


@pytest.mark.django_db
@responses.activate
def test_create_data_sync(data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    data_syncs = list(DataSync.objects.all())
    assert len(data_syncs) == 1
    data_sync = data_syncs[0].specific
    assert data_sync.ical_url == "https://baserow.io/ical.ics"

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )

    assert response.json() == {
        "id": data_sync.table_id,
        "name": "Test 1",
        "order": 1,
        "database_id": database.id,
        "data_sync": {
            "id": data_sync.id,
            "type": "ical_calendar",
            "auto_add_new_properties": False,
            "two_way_sync": False,
            "synced_properties": [
                {
                    "field_id": properties[0].field_id,
                    "key": "uid",
                    "unique_primary": True,
                },
                {
                    "field_id": properties[1].field_id,
                    "key": "dtstart",
                    "unique_primary": False,
                },
                {
                    "field_id": properties[2].field_id,
                    "key": "dtend",
                    "unique_primary": False,
                },
                {
                    "field_id": properties[3].field_id,
                    "key": "summary",
                    "unique_primary": False,
                },
            ],
            "last_sync": None,
            "last_error": None,
        },
    }


@pytest.mark.django_db
@responses.activate
def test_create_data_sync_with_auto_add_new_properties(data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid"],
            "auto_add_new_properties": True,
            "two_way_sync": False,
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    data_syncs = list(DataSync.objects.all())
    assert len(data_syncs) == 1
    data_sync = data_syncs[0].specific
    assert data_sync.auto_add_new_properties is True
    assert data_sync.ical_url == "https://baserow.io/ical.ics"

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )

    assert response.json() == {
        "id": data_sync.table_id,
        "name": "Test 1",
        "order": 1,
        "database_id": database.id,
        "data_sync": {
            "id": data_sync.id,
            "type": "ical_calendar",
            "auto_add_new_properties": True,
            "two_way_sync": False,
            "synced_properties": [
                {
                    "field_id": properties[0].field_id,
                    "key": "uid",
                    "unique_primary": True,
                },
            ],
            "last_sync": None,
            "last_error": None,
        },
    }


@pytest.mark.django_db
@pytest.mark.undo_redo
@responses.activate
def test_can_undo_redo_create_data_sync(api_client, data_fixture):
    same_session_id = "test"

    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    assert response.status_code == HTTP_200_OK

    data_sync = DataSync.objects.all().first()

    api_client.patch(
        reverse("api:user:undo"),
        {
            "scopes": {
                "table": data_sync.table_id,
                "application": data_sync.table.database_id,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    assert response.status_code == HTTP_200_OK

    data_sync.table.refresh_from_db()
    assert data_sync.table.trashed is True

    api_client.patch(
        reverse("api:user:redo"),
        {
            "scopes": {
                "table": data_sync.table_id,
                "application": data_sync.table.database_id,
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=same_session_id,
    )
    assert response.status_code == HTTP_200_OK

    data_sync.table.refresh_from_db()
    assert data_sync.table.trashed is False


@pytest.mark.django_db
def test_update_data_sync_no_permissions(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "synced_properties": ["uid", "dtstart", "summary"],
            "ical_url": "http://localhost/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_update_data_sync_invalid_synced_properties(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "synced_properties": ["TEST"],
            "ical_url": "http://localhost/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["synced_properties"]) == 1
    assert response_json["synced_properties"][0]["key"] == "uid"


@pytest.mark.django_db
def test_update_data_sync_not_existing_data_sync(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": 0})
    response = api_client.patch(
        url,
        {
            "synced_properties": ["TEST"],
            "ical_url": "http://localhost/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    response_json = response.json()
    assert response_json["error"] == "ERROR_DATA_SYNC_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_data_sync_invalid_kwargs(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "synced_properties": ["TEST"],
            "ical_url": "TEST",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ical_url"][0]["code"] == "invalid"


@pytest.mark.django_db
def test_update_data_sync_not_providing_anything(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "id": data_sync.id,
        "type": "ical_calendar",
        "auto_add_new_properties": False,
        "two_way_sync": False,
        "synced_properties": [
            {
                "field_id": data_sync.table.field_set.all().first().id,
                "key": "uid",
                "unique_primary": True,
            }
        ],
        "last_sync": None,
        "last_error": None,
    }


@pytest.mark.django_db
def test_update_data_sync(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "synced_properties": ["uid", "dtstart", "summary"],
            "ical_url": "http://localhost/ics.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "id": data_sync.id,
        "type": "ical_calendar",
        "auto_add_new_properties": False,
        "two_way_sync": False,
        "synced_properties": [
            {
                "field_id": properties[0].field_id,
                "key": "uid",
                "unique_primary": True,
            },
            {
                "field_id": properties[1].field_id,
                "key": "dtstart",
                "unique_primary": False,
            },
            {
                "field_id": properties[2].field_id,
                "key": "summary",
                "unique_primary": False,
            },
        ],
        "last_sync": None,
        "last_error": None,
    }


@pytest.mark.django_db
def test_update_data_sync_auto_add_new_properties(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "auto_add_new_properties": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["auto_add_new_properties"] is True

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "auto_add_new_properties": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["auto_add_new_properties"] is False


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_invalid_data_sync(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )

    response = api_client.post(
        reverse("api:database:data_sync:sync_table", kwargs={"data_sync_id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DATA_SYNC_DOES_NOT_EXIST"


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_failed_sync(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    api_client.post(
        reverse(
            "api:database:data_sync:sync_table",
            kwargs={"data_sync_id": data_sync_id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    job = SyncDataSyncTableJob.objects.all().first()

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "failed"
    assert job["type"] == "sync_data_sync_table"
    assert job["progress_percentage"] > 0
    assert job["data_sync"]["id"] == data_sync_id
    assert (
        job["human_readable_error"]
        == "The request to the URL didn't respond with an OK response code."
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_already_running(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    cache.add(f"data_sync_{data_sync_id}_syncing_table", "locked", timeout=2)

    job = SyncDataSyncTableJob.objects.create(data_sync_id=data_sync_id, user=user)
    run_async_job(job.id)

    job.refresh_from_db()
    assert job.human_readable_error == "The sync data sync job is already running."


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_unauthorized(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    user_2, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    response = api_client.post(
        reverse(
            "api:database:data_sync:sync_table", kwargs={"data_sync_id": data_sync_id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_unauthorized_after_job_created(
    api_client, data_fixture
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    job = SyncDataSyncTableJob.objects.create(data_sync_id=data_sync_id, user=user)
    WorkspaceUser.objects.all().delete()
    run_async_job(job.id)


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_job_with_trashed_table(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    job = SyncDataSyncTableJob.objects.create(data_sync_id=data_sync_id, user=user)

    data_sync = DataSync.objects.get(pk=data_sync_id)
    TableHandler().delete_table(user, data_sync.table)

    run_async_job(job.id)

    data_sync.refresh_from_db()
    # We expect nothing to have happened because table is trashed.
    assert data_sync.last_sync is None
    assert data_sync.last_error is None


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table_job_with_deleted_table(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    job = SyncDataSyncTableJob.objects.create(data_sync_id=data_sync_id, user=user)

    data_sync = DataSync.objects.get(pk=data_sync_id)
    data_sync.table.delete()

    run_async_job(job.id)

    assert DataSync.objects.all().count() == 0


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_async_sync_data_sync_table(api_client, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    response = api_client.post(
        reverse(
            "api:database:data_sync:sync_table", kwargs={"data_sync_id": data_sync_id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "sync_data_sync_table"
    assert job["progress_percentage"] == 0
    assert job["data_sync"]["id"] == data_sync_id

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "sync_data_sync_table"
    assert job["progress_percentage"] == 100
    assert job["data_sync"]["id"] == data_sync_id
    assert job["data_sync"]["last_error"] is None

    data_sync = DataSync.objects.get(pk=data_sync_id)
    model = data_sync.table.get_model()
    sync_1_rows = list(model.objects.all())

    fields = {
        p.key: p.field
        for p in DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
    }

    assert len(sync_1_rows) == 1
    assert (
        getattr(sync_1_rows[0], f"field_{fields['uid'].id}")
        == "1725220374375-34056@ical.marudot.com"
    )
    assert getattr(sync_1_rows[0], f"field_{fields['dtstart'].id}") == datetime(
        2024, 9, 1, 8, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_1_rows[0], f"field_{fields['dtend'].id}") == datetime(
        2024, 9, 1, 9, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_1_rows[0], f"field_{fields['summary'].id}") == "Test event 0"


@pytest.mark.django_db
def test_get_data_sync_properties_unauthorized(data_fixture, api_client):
    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "ical_calendar",
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_data_sync_properties_invalid_data(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "ical_calendar",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["ical_url"][0]["code"] == "required"


@pytest.mark.django_db
@responses.activate
def test_get_data_sync_properties(data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "ical_calendar",
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "uid",
            "name": "Unique ID",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "dtstart",
            "name": "Start date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "dtend",
            "name": "End date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "summary",
            "name": "Summary",
            "field_type": "text",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db
def test_get_data_sync_properties_of_data_sync_unauthorized(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    url = reverse(
        "api:database:data_sync:properties_of_data_sync",
        kwargs={"data_sync_id": data_sync_id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_data_sync_properties_of_data_sync_no_permissions(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    user_2, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user_2)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    url = reverse(
        "api:database:data_sync:properties_of_data_sync",
        kwargs={"data_sync_id": data_sync_id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_data_sync_properties_of_data_sync_does_not_exist(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )

    url = reverse(
        "api:database:data_sync:properties_of_data_sync", kwargs={"data_sync_id": 0}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
@responses.activate
def test_get_data_sync_properties_of_data_sync(data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    url = reverse(
        "api:database:data_sync:properties_of_data_sync",
        kwargs={"data_sync_id": data_sync_id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "uid",
            "name": "Unique ID",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "dtstart",
            "name": "Start date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "dtend",
            "name": "End date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "summary",
            "name": "Summary",
            "field_type": "text",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db
def test_get_data_sync_not_found(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": 0})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    response_json = response.json()
    assert response_json["error"] == "ERROR_DATA_SYNC_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_data_sync_no_permission(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    user_2, token_2 = data_fixture.create_user_and_token(
        email="test_2@test.nl", password="password", first_name="Test1"
    )
    database = data_fixture.create_database_application(user=user_2)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid", "dtstart", "dtend", "summary"],
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync_id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_get_data_sync(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io",
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "id": data_sync.id,
        "type": "ical_calendar",
        "auto_add_new_properties": False,
        "two_way_sync": False,
        "synced_properties": [
            {
                "field_id": data_sync.table.field_set.all().first().id,
                "key": "uid",
                "unique_primary": True,
            }
        ],
        "last_sync": None,
        "last_error": None,
        "ical_url": "https://baserow.io",
    }


@pytest.mark.django_db
def test_create_data_sync_with_two_way_sync_unsupported_type(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "ical_calendar",
            "synced_properties": ["uid"],
            "two_way_sync": True,
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_TWO_WAY_DATA_SYNC_NOT_SUPPORTED"
    assert (
        "Two-way sync is not supported for this data sync type"
        in response_json["detail"]
    )


@pytest.mark.django_db
def test_update_data_sync_enable_two_way_sync_unsupported_type(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io",
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
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_TWO_WAY_DATA_SYNC_NOT_SUPPORTED"
    assert (
        "Two-way sync is not supported for this data sync type"
        in response_json["detail"]
    )


@pytest.mark.django_db(transaction=True)
def test_cannot_create_row_without_two_way_data_sync(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id"],
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
    table_id = response.json()["id"]

    response = api_client.post(
        reverse("api:database:rows:list", kwargs={"table_id": table_id}),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_CANNOT_CREATE_ROWS_IN_TABLE"


@pytest.mark.django_db(transaction=True)
def test_cannot_delete_row_without_two_way_data_sync(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id"],
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
    table_id = response.json()["id"]

    url = reverse("api:database:rows:item", kwargs={"table_id": table_id, "row_id": 1})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_ROWS_IN_TABLE"
