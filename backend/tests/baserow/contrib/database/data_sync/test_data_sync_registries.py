import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import ICalCalendarDataSync
from baserow.core.registries import ImportExportConfig, application_type_registry

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
@responses.activate
def test_import_export_data_sync(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )
    properties = data_sync.synced_properties.all().order_by("key")
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    imported_workspace = data_fixture.create_workspace()
    imported_workspace_user = data_fixture.create_user_workspace(
        workspace=imported_workspace, user=user
    )
    id_mapping = {}

    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        id_mapping,
        None,
        None,
    )

    imported_table = imported_database.table_set.all().first()
    assert imported_table.id != data_sync.table.id

    imported_data_sync = imported_table.data_sync.specific
    assert id_mapping["database_table_data_sync"][data_sync.id] == imported_data_sync.id
    assert isinstance(imported_data_sync, ICalCalendarDataSync)
    assert imported_data_sync.ical_url == data_sync.ical_url
    assert imported_data_sync.last_sync == data_sync.last_sync
    assert imported_data_sync.last_error == data_sync.last_error

    imported_properties = imported_data_sync.synced_properties.all().order_by("key")
    assert imported_properties[0].field_id != properties[0].field_id
    assert imported_properties[0].field.table_id == imported_table.id
    assert imported_properties[0].key == properties[0].key == "dtend"
    assert imported_properties[1].key == properties[1].key == "dtstart"
    assert imported_properties[2].key == properties[2].key == "summary"
    assert imported_properties[3].key == properties[3].key == "uid"

    fields = imported_data_sync.table.field_set.all().order_by("id")
    assert fields[0].read_only is True
    assert fields[1].read_only is True
    assert fields[2].read_only is True
    assert fields[3].read_only is True


@pytest.mark.django_db
@responses.activate
def test_base_data_sync_settings_are_preserved_on_import_export(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=ICAL_FEED_WITH_ONE_ITEMS,
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="ical_calendar",
        synced_properties=["uid"],
        auto_add_new_properties=True,  # default False
        delete_unmatched_rows=False,  # default True
        ical_url="https://baserow.io/ical.ics",
    )
    # `two_way_sync` can't be enabled through the handler for iCal (no two-way sync
    # strategy), so set it directly to still cover it in the serialization round-trip.
    data_sync.two_way_sync = True  # default False
    data_sync.save()

    assert data_sync.auto_add_new_properties is True
    assert data_sync.delete_unmatched_rows is False
    assert data_sync.two_way_sync is True

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    imported_workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(workspace=imported_workspace, user=user)

    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        {},
        None,
        None,
    )

    imported_table = imported_database.table_set.all().first()
    imported_data_sync = imported_table.data_sync.specific

    assert imported_data_sync.auto_add_new_properties is True
    assert imported_data_sync.delete_unmatched_rows is False
    assert imported_data_sync.two_way_sync is True
