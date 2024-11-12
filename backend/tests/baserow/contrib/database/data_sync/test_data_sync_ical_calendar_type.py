from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
import responses
from freezegun import freeze_time

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.utils import compare_date

ICAL_FEED_WITH_ONE_ITEMS_WITHOUT_DTEND = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:Baserow / baserow.io
NAME:Calendar
X-WR-CALNAME:Calendar
X-WR-TIMEZONE:UTC
BEGIN:VEVENT
SUMMARY:row 1 - 01/09/2024
DTSTART;VALUE=DATE:20240901
DTSTAMP:20240913T130754Z
UID:http://localhost:3000/database/501/table/1436/5160/row/1
DESCRIPTION:row 1 - 01/09/2024
LAST-MODIFIED:20240913T130754Z
LOCATION:http://localhost:3000/database/501/table/1436/5160/row/1
END:VEVENT
END:VCALENDAR
"""


@pytest.mark.django_db
@responses.activate
def test_ical_sync_data_sync_table_without_dtend(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS_WITHOUT_DTEND,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )
    with freeze_time("2021-01-01 12:00"):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = {
        p.key: p.field
        for p in DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
    }

    model = data_sync.table.get_model()
    sync_1_rows = list(model.objects.all())

    assert len(sync_1_rows) == 1
    assert (
        getattr(sync_1_rows[0], f"field_{fields['uid'].id}")
        == "http://localhost:3000/database/501/table/1436/5160/row/1"
    )
    assert getattr(sync_1_rows[0], f"field_{fields['dtstart'].id}") == datetime(
        2024, 9, 1, 0, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_1_rows[0], f"field_{fields['dtend'].id}") is None


@pytest.mark.django_db
def test_ical_sync_date_equal(data_fixture):
    amsterdam = ZoneInfo("Europe/Amsterdam")

    equal_dates = [
        datetime(2024, 9, 13, 12, 30, 1),
        datetime(2024, 9, 13, 12, 30, 59),
        datetime(2024, 9, 13, 12, 30, 30, tzinfo=timezone.utc),
        datetime(2024, 9, 13, 14, 30, 30, tzinfo=amsterdam),
        date(2024, 9, 13),
    ]

    for index, d1 in enumerate(equal_dates):
        for index2, d2 in enumerate(equal_dates):
            if index != index2:
                assert compare_date(d1, d2)


@pytest.mark.django_db
def test_ical_sync_date_not_equal(data_fixture):
    amsterdam = ZoneInfo("Europe/Amsterdam")

    not_equal_dates = [
        datetime(2024, 9, 13, 12, 30, 1),
        datetime(2024, 9, 13, 12, 29, 59),
        datetime(2024, 9, 13, 12, 31, 1, tzinfo=timezone.utc),
        datetime(2024, 9, 13, 14, 32, 1, tzinfo=amsterdam),
        date(2024, 9, 14),
    ]

    for index, d1 in enumerate(not_equal_dates):
        for index2, d2 in enumerate(not_equal_dates):
            if index != index2:
                assert not compare_date(d1, d2)
