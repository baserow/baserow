from datetime import datetime, timezone
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection

import pytest
import responses
from freezegun import freeze_time

from baserow.contrib.database.data_sync.exceptions import (
    PropertyNotFound,
    SyncDataSyncTableAlreadyRunning,
    UniquePrimaryPropertyNotFound,
)
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.ical_data_sync_type import (
    ICalCalendarDataSyncType,
    UIDICalCalendarDataSyncProperty,
)
from baserow.contrib.database.data_sync.models import (
    DataSync,
    DataSyncSyncedProperty,
    ICalCalendarDataSync,
)
from baserow.contrib.database.data_sync.registries import DataSyncTypeRegistry
from baserow.contrib.database.fields.exceptions import CannotDeletePrimaryField
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, LongTextField, TextField
from baserow.contrib.database.views.models import GridView
from baserow.core.db import specific_iterator
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.models import TrashEntry

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

ICAL_FEED_WITH_ONE_ITEMS_WITHOUT_DTEND = """BEGIN:VCALENDAR
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
SUMMARY:Test event 0
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
END:VCALENDAR"""

ICAL_FEED_WITH_TWO_ITEMS = """BEGIN:VCALENDAR
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
END:V
BEGIN:VEVENT
DTSTAMP:20240901T195345Z
UID:1725220374375-34056@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240901T100000
DTEND;TZID=Europe/Berlin:20240901T110000
SUMMARY:Test event 1
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20240901T195345Z
UID:1725220387555-95757@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240902T130000
DTEND;TZID=Europe/Berlin:20240902T150000
SUMMARY:Test event 2
DESCRIPTION:Test description 2
LOCATION:London
END:VEVENT
END:VCALENDAR"""

ICAL_FEED_WITH_TWO_ITEMS_SAME_ID = """BEGIN:VCALENDAR
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
DTSTAMP:20240901T195345Z
UID:1725220387555-95757@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240901T100000
DTEND;TZID=Europe/Berlin:20240901T110000
SUMMARY:Test event 1
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20240901T195345Z
UID:1725220387555-95757@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240902T130000
DTEND;TZID=Europe/Berlin:20240902T150000
SUMMARY:Test event 2
DESCRIPTION:Test description 2
LOCATION:London
END:VEVENT
END:VCALENDAR"""

ICAL_FEED_WITH_THREE_ITEMS = """BEGIN:VCALENDAR
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
DTSTAMP:20240901T195505Z
UID:1725220374375-34056@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240901T110000
DTEND;TZID=Europe/Berlin:20240901T120000
SUMMARY:Test event 1
URL:https://baserow.io
DESCRIPTION:Test description 1
LOCATION:Amsterdam
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20240901T195505Z
UID:1725220387555-95757@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240902T130000
DTEND;TZID=Europe/Berlin:20240902T150000
SUMMARY:Test event 2
DESCRIPTION:Test description 2
LOCATION:London
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20240901T195505Z
UID:1725220480937-57370@ical.marudot.com
DTSTART;TZID=Europe/Berlin:20240902T160000
DTEND;TZID=Europe/Berlin:20240903T210000
SUMMARY:Test event 3
DESCRIPTION:Test description 3
LOCATION:Berlin
END:VEVENT
END:VCALENDAR"""


@pytest.mark.django_db
def test_create_data_sync_table_invalid_property(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    with pytest.raises(PropertyNotFound):
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="ical_calendar",
            synced_properties=["does_not_exist"],
        )


@pytest.mark.django_db
def test_create_data_sync_table_no_unique_primary(data_fixture):
    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        # Intentionally remove the `unique_primary` properties to trigger the
        # exception when creating.
        def get_properties(self, *args, **kwargs) -> dict:
            return [
                p
                for p in super().get_properties(*args, **kwargs)
                if not p.unique_primary
            ]

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        user = data_fixture.create_user()
        database = data_fixture.create_database_application(user=user)

        handler = DataSyncHandler()

        with pytest.raises(UniquePrimaryPropertyNotFound):
            handler.create_data_sync_table(
                user=user,
                database=database,
                table_name="Test",
                type_name="ical_calendar",
                synced_properties=["summary"],
            )


@pytest.mark.django_db
def test_create_data_sync_table_without_permissions(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application()

    handler = DataSyncHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="ical_calendar",
            synced_properties=["summary"],
        )


@pytest.mark.django_db
def test_create_data_sync_table_with_the_multiple_same_properties(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "uid"],
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert DataSyncSyncedProperty.objects.filter(data_sync=data_sync).count() == 1


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_data_sync_table(send_mock, data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://baserow.io",
    )

    assert isinstance(data_sync, ICalCalendarDataSync)
    assert data_sync.id
    assert data_sync.table.name == "Test"
    assert data_sync.table.database_id == database.id
    assert data_sync.ical_url == "https://baserow.io"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 4
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], TextField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[1].name == "Start date"
    assert fields[1].primary is False
    assert fields[1].date_format == "ISO"
    assert fields[1].date_include_time is True
    assert fields[1].date_time_format == "24"
    assert fields[1].date_show_tzinfo is True
    assert fields[1].read_only is True
    assert fields[1].immutable_properties is False
    # assert fields[1].date_force_timezone is False # @TODO fix this
    assert fields[2].name == "End date"
    assert fields[2].primary is False
    assert fields[2].read_only is True
    assert fields[3].name == "Summary"
    assert fields[3].primary is False
    assert fields[3].read_only is True

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )
    assert len(properties) == 4
    assert properties[0].key == "uid"
    assert properties[0].field_id == fields[0].id
    assert properties[1].key == "dtstart"
    assert properties[1].field_id == fields[1].id
    assert properties[2].key == "dtend"
    assert properties[2].field_id == fields[2].id
    assert properties[3].key == "summary"
    assert properties[3].field_id == fields[3].id

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == data_sync.table_id
    assert send_mock.call_args[1]["user"] == user

    model = data_sync.table.get_model()
    # Has to be `len` and not `.count()` to make sure the cell values are actually
    # returned.
    assert len(model.objects.all()) == 0


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_data_sync_table_automatically_add_unique_properties(
    send_mock, data_fixture
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["dtstart"],
        ical_url="https://baserow.io",
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], TextField)
    assert fields[0].primary is True
    assert fields[1].name == "Start date"
    assert fields[1].primary is False


@pytest.mark.django_db
def test_update_data_sync_table_without_permissions(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
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

    with pytest.raises(UserNotInWorkspace):
        DataSyncHandler().update_data_sync_table(
            user=user_2,
            data_sync=data_sync,
            synced_properties=["uid", "dtstart", "summary"],
            ical_url="http://localhost/ics.ics",
        )


@pytest.mark.django_db
@patch("baserow.contrib.database.table.signals.table_updated.send")
def test_update_data_sync_table(send_mock, data_fixture):
    user = data_fixture.create_user()
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

    data_sync = handler.update_data_sync_table(
        user=user,
        data_sync=data_sync,
        synced_properties=["uid", "dtstart", "summary"],
        ical_url="http://localhost/ics.ics",
    )

    assert isinstance(data_sync, ICalCalendarDataSync)
    assert data_sync.id
    assert data_sync.table.name == "Test"
    assert data_sync.table.database_id == database.id
    assert data_sync.ical_url == "http://localhost/ics.ics"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 3
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], TextField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[1].name == "Start date"
    assert fields[1].primary is False
    assert fields[1].date_format == "ISO"
    assert fields[1].date_include_time is True
    assert fields[1].date_time_format == "24"
    assert fields[1].date_show_tzinfo is True
    assert fields[1].read_only is True
    assert fields[1].immutable_properties is False
    assert fields[2].name == "Summary"
    assert fields[2].primary is False
    assert fields[2].read_only is True

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )
    assert len(properties) == 3
    assert properties[0].key == "uid"
    assert properties[0].field_id == fields[0].id
    assert properties[1].key == "dtstart"
    assert properties[1].field_id == fields[1].id
    assert properties[2].key == "summary"
    assert properties[2].field_id == fields[2].id

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == data_sync.table_id
    assert send_mock.call_args[1]["user"] == user


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_create_update_delete_row(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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

    views = list(data_sync.table.view_set.all())
    assert len(views) == 1
    assert isinstance(views[0].specific, GridView)

    model = data_sync.table.get_model()
    sync_1_rows = list(model.objects.all())

    assert len(sync_1_rows) == 2
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
    assert getattr(sync_1_rows[0], f"field_{fields['summary'].id}") == "Test event 1"
    assert (
        getattr(sync_1_rows[1], f"field_{fields['uid'].id}")
        == "1725220387555-95757@ical.marudot.com"
    )

    assert data_sync.last_sync.year == 2021
    assert data_sync.last_sync.month == 1
    assert data_sync.last_sync.day == 1

    # Test updating rows
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_THREE_ITEMS,
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    sync_2_rows = list(model.objects.all())

    assert len(sync_2_rows) == 3
    assert sync_1_rows[0].id == sync_2_rows[0].id
    assert sync_1_rows[1].id == sync_2_rows[1].id
    assert (
        getattr(sync_2_rows[0], f"field_{fields['uid'].id}")
        == "1725220374375-34056@ical.marudot.com"
    )
    assert getattr(sync_2_rows[0], f"field_{fields['dtstart'].id}") == datetime(
        2024, 9, 1, 9, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_2_rows[0], f"field_{fields['dtend'].id}") == datetime(
        2024, 9, 1, 10, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_2_rows[0], f"field_{fields['summary'].id}") == "Test event 1"
    assert (
        getattr(sync_2_rows[1], f"field_{fields['uid'].id}")
        == "1725220387555-95757@ical.marudot.com"
    )
    assert (
        getattr(sync_2_rows[2], f"field_{fields['uid'].id}")
        == "1725220480937-57370@ical.marudot.com"
    )

    # Test deleting rows
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    sync_3_rows = list(model.objects.all())

    assert len(sync_3_rows) == 1
    assert sync_3_rows[0].id == sync_2_rows[0].id == sync_1_rows[0].id
    assert (
        getattr(sync_3_rows[0], f"field_{fields['uid'].id}")
        == "1725220374375-34056@ical.marudot.com"
    )
    assert getattr(sync_3_rows[0], f"field_{fields['dtstart'].id}") == datetime(
        2024, 9, 1, 8, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_3_rows[0], f"field_{fields['dtend'].id}") == datetime(
        2024, 9, 1, 9, 0, tzinfo=timezone.utc
    )
    assert getattr(sync_3_rows[0], f"field_{fields['summary'].id}") == "Test event 0"


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_property_removed_from_data_sync_type(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync_handler = DataSyncHandler()
    data_sync = data_sync_handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = [
                p for p in super().get_properties(*args, **kwargs) if p.key != "dtstart"
            ]
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.sync_data_sync_table(
            user=user,
            data_sync=data_sync,
        )

    fields = {
        p.key: p.field
        for p in DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
    }

    model = data_sync.table.get_model()
    sync_rows = list(model.objects.all())

    assert data_sync.table.field_set.all().count() == 1
    assert len(sync_rows) == 1
    assert (
        getattr(sync_rows[0], f"field_{fields['uid'].id}")
        == "1725220374375-34056@ical.marudot.com"
    )


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_multiple_unique_primary_properties(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS_SAME_ID,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync_handler = DataSyncHandler()
    data_sync = data_sync_handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            for p in properties:
                if p.key == "summary":
                    p.unique_primary = True
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.sync_data_sync_table(
            user=user,
            data_sync=data_sync,
        )

    fields = {
        p.key: p.field
        for p in DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
    }

    model = data_sync.table.get_model()
    sync_rows = list(model.objects.all())

    assert data_sync.table.field_set.all().count() == 2
    assert len(sync_rows) == 2
    assert (
        getattr(sync_rows[0], f"field_{fields['uid'].id}")
        == "1725220387555-95757@ical.marudot.com"
    )
    assert getattr(sync_rows[0], f"field_{fields['summary'].id}") == "Test event 1"
    assert (
        getattr(sync_rows[1], f"field_{fields['uid'].id}")
        == "1725220387555-95757@ical.marudot.com"
    )
    assert getattr(sync_rows[1], f"field_{fields['summary'].id}") == "Test event 2"


@pytest.mark.django_db
@responses.activate
@patch("baserow.contrib.database.table.signals.table_updated.send")
def test_sync_data_sync_table_refresh_called(send_mock, data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["table"].id == data_sync.table_id
    assert send_mock.call_args[1]["user"].id == user.id
    assert send_mock.call_args[1]["force_table_refresh"] is True


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_sync_error(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert data_sync.last_sync is None
    assert (
        data_sync.last_error
        == "The request to the URL didn't respond with an OK response code."
    )


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.data_sync.ical_data_sync_type.ICalCalendarDataSyncType.get_all_rows"
)
def test_sync_data_sync_table_exception_raised(mock_get_all_rows, data_fixture):
    mock_get_all_rows.side_effect = ValueError

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

    with pytest.raises(ValueError):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_with_formula_field_dependency(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
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
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    formula = FieldHandler().create_field(
        user,
        table=data_sync.table,
        type_name="formula",
        name="formula",
        formula=f"field('Summary')",
    )

    model = data_sync.table.get_model()
    assert getattr(model.objects.all().first(), f"field_{formula.id}") == "Test event 0"

    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert getattr(rows[0], f"field_{formula.id}") == "Test event 1"
    assert getattr(rows[1], f"field_{formula.id}") == "Test event 2"


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_without_all_fields_rows_updated(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # Trigger for a second time to check when row is updated.
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.last_sync


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_without_permissions(data_fixture):
    user = data_fixture.create_user()

    data_sync = data_fixture.create_ical_data_sync(
        ical_url="https://baserow.io/ical.ics",
    )

    with pytest.raises(UserNotInWorkspace):
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_already_running(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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

    cache.add(f"data_sync_{data_sync.id}_syncing_table", "locked", timeout=2)

    with pytest.raises(SyncDataSyncTableAlreadyRunning):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_lock_is_removed(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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

    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert cache.get(f"data_sync_{data_sync.id}_syncing_table") != "locked"


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_lock_is_removed_on_sync_error(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_error
    assert cache.get(f"data_sync_{data_sync.id}_syncing_table") != "locked"


@pytest.mark.django_db
@responses.activate
def test_sync_data_sync_table_lock_is_removed_on_failure(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body=ICAL_FEED_WITH_TWO_ITEMS,
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

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_all_rows(self, *args, **kwargs) -> dict:
            raise ValueError("test")

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        with pytest.raises(ValueError):
            handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert cache.get(f"data_sync_{data_sync.id}_syncing_table") != "locked"


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_not_existing_property(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    with pytest.raises(PropertyNotFound):
        handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["test"],
        )


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_without_permissions(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()

    data_sync = data_fixture.create_ical_data_sync(
        ical_url="https://baserow.io/ical.ics",
    )
    with pytest.raises(UserNotInWorkspace):
        handler = DataSyncHandler()
        handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["uid", "dtend", "summary"],
        )


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_field_name_already_exists(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync_handler = DataSyncHandler()

    data_sync = data_sync_handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )
    data_fixture.create_text_field(user, table=data_sync.table, name="Summary")
    data_sync_handler.set_data_sync_synced_properties(
        user=user,
        data_sync=data_sync,
        synced_properties=["uid", "dtstart", "summary"],
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 4
    assert fields[3].name == "Summary 2"


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_field_types_changed(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync_handler = DataSyncHandler()
    data_sync = data_sync_handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io/ical.ics",
    )

    registry = DataSyncTypeRegistry()

    class TmpUIDICalCalendarDataSyncProperty(UIDICalCalendarDataSyncProperty):
        def to_baserow_field(self) -> TextField:
            return LongTextField(name=self.name)

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            properties[0] = TmpUIDICalCalendarDataSyncProperty("uid", "Unique ID")
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["uid"],
        )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], LongTextField)


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_property_removed_from_data_sync(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    data_sync_handler = DataSyncHandler()
    data_sync = data_sync_handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = [
                p for p in super().get_properties(*args, **kwargs) if p.key != "dtstart"
            ]
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["uid"],
        )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], TextField)


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_property_immutable_properties_changed(
    data_fixture,
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            for p in properties:
                if p.key == "dtstart":
                    p.immutable_properties = True
            return properties

    registry.register(TmpICalCalendarDataSync())

    data_sync_handler = DataSyncHandler()

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync = data_sync_handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="ical_calendar",
            synced_properties=["uid", "dtstart"],
            ical_url="https://baserow.io/ical.ics",
        )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[1].immutable_properties is True

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            for p in properties:
                if p.key == "dtstart":
                    p.immutable_properties = False
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["uid", "dtstart"],
        )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[1].immutable_properties is False


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_property_unique_primary_changed(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            for p in properties:
                if p.key == "uid":
                    p.unique_primary = True
                if p.key == "dtstart":
                    p.unique_primary = False
            return properties

    registry.register(TmpICalCalendarDataSync())

    data_sync_handler = DataSyncHandler()

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync = data_sync_handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="ical_calendar",
            synced_properties=["uid", "dtstart"],
            ical_url="https://baserow.io/ical.ics",
        )

    properties = data_sync.synced_properties.all().order_by("id")
    assert len(properties) == 2
    assert properties[1].unique_primary is False

    registry = DataSyncTypeRegistry()

    class TmpICalCalendarDataSync(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs) -> dict:
            properties = super().get_properties(*args, **kwargs)
            for p in properties:
                if p.key == "uid":
                    p.unique_primary = False
                if p.key == "dtstart":
                    p.unique_primary = True
            return properties

    registry.register(TmpICalCalendarDataSync())

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=registry,
    ):
        data_sync_handler.set_data_sync_synced_properties(
            user=user,
            data_sync=data_sync,
            synced_properties=["uid", "dtstart"],
        )

    properties = data_sync.synced_properties.all().order_by("id")
    assert len(properties) == 2
    assert properties[1].unique_primary is True


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_with_multiple_same_synced_properties(
    data_fixture,
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    handler.set_data_sync_synced_properties(
        user=user,
        data_sync=data_sync,
        synced_properties=["uid", "uid"],
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert DataSyncSyncedProperty.objects.filter(data_sync=data_sync).count() == 1


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    handler.set_data_sync_synced_properties(
        user=user,
        data_sync=data_sync,
        synced_properties=["uid", "dtend", "summary"],
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 3
    assert fields[0].name == "Unique ID"
    assert isinstance(fields[0], TextField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].name == "End date"
    assert fields[1].primary is False
    assert fields[1].read_only is True
    assert fields[2].name == "Summary"
    assert fields[2].primary is False
    assert fields[2].read_only is True
    assert fields[2].immutable_properties is True

    properties = DataSyncSyncedProperty.objects.filter(data_sync=data_sync).order_by(
        "id"
    )
    assert len(properties) == 3
    assert properties[0].key == "uid"
    assert properties[0].field_id == fields[0].id
    assert properties[1].key == "dtend"
    assert properties[1].field_id == fields[1].id
    assert properties[2].key == "summary"
    assert properties[2].field_id == fields[2].id


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_synced_properties_correctly_removing_field(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'database_table_{data_sync.table_id}'"""
        )
        before_number_of_columns = cursor.fetchone()[0]

    handler.set_data_sync_synced_properties(
        user=user,
        data_sync=data_sync,
        synced_properties=["uid"],
    )

    assert Field.objects_and_trash.filter(table=data_sync.table).count() == 1
    assert TrashEntry.objects.all().count() == 0

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'database_table_{data_sync.table_id}'"""
        )
        after_number_of_columns = cursor.fetchone()[0]

    assert after_number_of_columns == before_number_of_columns - 1


@pytest.mark.django_db
@responses.activate
def test_delete_sync_data_sync_table(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
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
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.table.delete()
    assert DataSync.objects.all().count() == 0
    assert DataSyncSyncedProperty.objects.all().count() == 0


@pytest.mark.django_db
@responses.activate
def test_delete_unique_primary_data_sync_field(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
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

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    unique_primary_field = fields[0]
    unique_primary_field.primary = False
    unique_primary_field.save()

    with pytest.raises(CannotDeletePrimaryField):
        FieldHandler().delete_field(user, unique_primary_field)


@pytest.mark.django_db
@responses.activate
def test_delete_non_unique_primary_data_sync_field(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
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

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    non_unique_primary_field = fields[1]

    FieldHandler().delete_field(user, non_unique_primary_field)

    assert data_sync.table.field_set.all().count() == 3


@pytest.mark.django_db
@responses.activate
def test_trash_field_and_then_sync(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    FieldHandler().delete_field(user, fields[1])

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert data_sync.last_error is None


@pytest.mark.django_db
@responses.activate
def test_trash_field_is_synced(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )
    responses.add(
        responses.GET,
        "https://baserow.io/ical2.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )
    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.ical_url = "https://baserow.io/ical2.ics"
    data_sync.save()
    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    FieldHandler().delete_field(user, fields[1])

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = model.objects.all()

    assert getattr(rows[1], f"field_{fields[1].id}") == datetime(
        2024, 9, 2, 11, 0, tzinfo=timezone.utc
    )


@pytest.mark.django_db
@responses.activate
def test_set_data_sync_not_recreate_trashed_field_property_on_sync(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_TWO_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart"],
        ical_url="https://baserow.io/ical.ics",
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    FieldHandler().delete_field(user, fields[1])

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert Field.objects_and_trash.filter(table=data_sync.table).count() == 2


@pytest.mark.field_duration
@pytest.mark.django_db
@responses.activate
def test_duplicate_data_sync_field(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io/ical.ics",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    duplicated_field, _ = FieldHandler().duplicate_field(
        user=user, field=fields[0], duplicate_data=True
    )

    assert duplicated_field.read_only is False
    assert duplicated_field.immutable_properties is False
    assert duplicated_field.immutable_type is False

    model = data_sync.table.get_model()
    rows = model.objects.all()

    assert getattr(rows[0], f"field_{duplicated_field.id}") == getattr(
        rows[0], f"field_{fields[0].id}"
    )
