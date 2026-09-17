from unittest.mock import patch

import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.ical_data_sync_type import (
    ICalCalendarDataSyncType,
)
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import DataSyncTypeRegistry
from baserow.core.jobs.handler import JobHandler

FEED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
DTSTAMP:20240901T195345Z
UID:uid-1
DTSTART:20240901T100000Z
DTEND:20240901T110000Z
SUMMARY:Event 1
END:VEVENT
END:VCALENDAR"""


def _registry_without_summary():
    """
    A registry whose ical type no longer reports `summary`, so the next sync sees
    that property as obsolete and would remove its field.
    """

    registry = DataSyncTypeRegistry()

    class WithoutSummary(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs):
            return [
                p for p in super().get_properties(*args, **kwargs) if p.key != "summary"
            ]

    registry.register(WithoutSummary())
    return registry


def _synced_data_sync(data_fixture, user, database):
    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    return data_sync


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_a_failed_sync_does_not_delete_a_column_the_source_stopped_reporting(
    data_fixture,
):
    """
    The schema phase used to remove obsolete properties before the fetch, and that
    removal permanently deletes the column and commits on its own. A run that then
    failed -- or a source that dropped a property for a single run -- would take a
    populated column with it, unrecoverably.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _synced_data_sync(data_fixture, user, database)

    summary_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="summary"
    ).field_id
    model = data_sync.table.get_model()
    assert getattr(model.objects.first(), f"field_{summary_field_id}") == "Event 1", (
        "the first sync did not populate the column this test is about"
    )

    registry = _registry_without_summary()
    data_sync_type = registry.get("ical_calendar")
    original_get_all_rows = type(data_sync_type).get_all_rows

    def failing_get_all_rows(self, instance, progress_builder=None):
        # Drain the real generator so the schema phase has fully committed,
        # then fail the way an unreachable source would.
        list(original_get_all_rows(self, instance, progress_builder=progress_builder))
        raise RuntimeError("fetch boom")

    type(data_sync_type).get_all_rows = failing_get_all_rows
    try:
        with patch(
            "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
            new=registry,
        ):
            with pytest.raises(RuntimeError):
                JobHandler().create_and_start_job(
                    user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
                )
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert data_sync.table.field_set.filter(id=summary_field_id).exists(), (
        "the sync failed, but the schema phase had already permanently deleted "
        "the column of the property the source stopped reporting, along with the "
        "data in it"
    )
    model = data_sync.table.get_model()
    assert getattr(model.objects.first(), f"field_{summary_field_id}") == "Event 1", (
        "the column survived the failed sync but its data did not"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_a_successful_sync_still_removes_a_property_the_source_dropped(data_fixture):
    """Deferring the removal must not turn into never removing anything."""

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _synced_data_sync(data_fixture, user, database)

    summary_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="summary"
    ).field_id

    with patch(
        "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
        new=_registry_without_summary(),
    ):
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    assert not DataSyncSyncedProperty.objects.filter(
        data_sync=data_sync, key="summary"
    ).exists(), "the obsolete property was never removed after a successful sync"
    assert not data_sync.table.field_set.filter(id=summary_field_id).exists(), (
        "the obsolete property is gone, but its field was left behind as an "
        "orphaned column"
    )
    assert data_sync.table.get_model().objects.count() == 1
