from unittest.mock import patch

import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.ical_data_sync_type import (
    ICalCalendarDataSyncType,
)
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import (
    DataSyncTypeRegistry,
    data_sync_type_registry,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.cache import (
    generated_models_cache,
    table_model_cache_entry_key,
)
from baserow.core.cache import local_cache

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

FEED_WITH_NEW_SUMMARY = FEED.replace("SUMMARY:Event 1", "SUMMARY:Event 1 renamed")


def _synced_data_sync(user, database, synced_properties):
    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=synced_properties,
        ical_url="https://baserow.io/ical.ics",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)
    return data_sync


def _registry_without_summary():
    registry = DataSyncTypeRegistry()

    class WithoutSummary(ICalCalendarDataSyncType):
        def get_properties(self, *args, **kwargs):
            return [
                p for p in super().get_properties(*args, **kwargs) if p.key != "summary"
            ]

    registry.register(WithoutSummary())
    return registry


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_a_property_the_source_dropped_is_removed_before_the_fetch(data_fixture):
    """
    The schema phase removes obsolete properties before the fetch. A source that
    fetches by the enabled properties would otherwise ask for a column it no
    longer has.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _synced_data_sync(user, database, ["uid", "summary"])

    summary_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="summary"
    ).field_id

    registry = _registry_without_summary()
    data_sync_type = registry.get("ical_calendar")
    original_get_all_rows = type(data_sync_type).get_all_rows
    seen = {}

    def observing_get_all_rows(self, instance, progress_builder=None):
        seen["field_exists"] = instance.table.field_set.filter(
            id=summary_field_id
        ).exists()
        return original_get_all_rows(self, instance, progress_builder=progress_builder)

    type(data_sync_type).get_all_rows = observing_get_all_rows
    try:
        with patch(
            "baserow.contrib.database.data_sync.handler.data_sync_type_registry",
            new=registry,
        ):
            DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert seen["field_exists"] is False, (
        "the obsolete column was still there when the fetch started"
    )
    data_sync.refresh_from_db()
    assert data_sync.last_error is None
    assert not DataSyncSyncedProperty.objects.filter(
        data_sync=data_sync, key="summary"
    ).exists()
    assert not data_sync.table.field_set.filter(id=summary_field_id).exists()
    assert data_sync.table.get_model().objects.count() == 1


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_a_property_enabled_during_the_fetch_is_written_by_that_sync(data_fixture):
    """
    A property enabled through the settings API while the fetch is in flight adds
    a column in another process. The write phase must see that column: the model
    it queries with is cached per thread, and the cache of this one was not
    invalidated by that request.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _synced_data_sync(user, database, ["uid", "dtstart", "summary"])
    assert not DataSyncSyncedProperty.objects.filter(
        data_sync=data_sync, key="dtend"
    ).exists()

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows
    enabled = {}

    def enabling_get_all_rows(self, instance, progress_builder=None):
        rows = list(
            original_get_all_rows(self, instance, progress_builder=progress_builder)
        )
        if not enabled:
            enabled["yes"] = True
            # The property is enabled by another process. That process bumps the
            # table version and clears its own thread-local cache, but not the
            # worker's, and it doesn't rebuild the shared model cache entry
            # either. Both are put back the way the worker left them.
            entry_key = table_model_cache_entry_key(instance.table_id)
            worker_local_cache = dict(local_cache._local.cache)
            shared_entry = generated_models_cache.get(entry_key)
            DataSyncHandler().set_data_sync_synced_properties(
                user, instance, synced_properties=["uid", "dtstart", "dtend", "summary"]
            )
            local_cache._local.cache = worker_local_cache
            generated_models_cache.set(entry_key, shared_entry, timeout=None)
        return rows

    type(data_sync_type).get_all_rows = enabling_get_all_rows
    try:
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert enabled, "the concurrent property change never ran"
    data_sync.refresh_from_db()
    assert data_sync.last_error is None, (
        f"a property enabled while the fetch was in flight failed the sync: "
        f"{data_sync.last_error}"
    )
    dtend_property = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="dtend"
    )
    assert data_sync.table.field_set.filter(id=dtend_property.field_id).exists(), (
        "the column enabled during the fetch was removed again by the sync"
    )
    row = data_sync.table.get_model(use_cache=False).objects.first()
    assert getattr(row, f"field_{dtend_property.field_id}") is not None, (
        "the source returned a value for the newly enabled property, but the sync "
        "did not write it"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_only_the_changed_cells_of_a_row_are_written(data_fixture):
    """
    The rows are not locked between the read and the write of the write phase,
    so a cell a user edits in that window is only safe when the sync doesn't
    write it. The update therefore carries the changed cells alone, not the
    whole row as it was read.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _synced_data_sync(user, database, ["uid", "dtstart", "summary"])
    summary_field_id = DataSyncSyncedProperty.objects.get(
        data_sync=data_sync, key="summary"
    ).field_id

    responses.replace(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body=FEED_WITH_NEW_SUMMARY,
    )

    original_update_rows = RowHandler.update_rows
    written = []

    def observing_update_rows(self, *args, **kwargs):
        written.extend(kwargs["rows_values"])
        return original_update_rows(self, *args, **kwargs)

    with patch.object(RowHandler, "update_rows", observing_update_rows):
        DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)

    assert len(written) == 1, "the changed summary was not written"
    assert set(written[0].keys()) == {"id", f"field_{summary_field_id}"}, (
        f"the update carried cells that did not change: {sorted(written[0])}"
    )
    row = data_sync.table.get_model().objects.first()
    assert getattr(row, f"field_{summary_field_id}") == "Event 1 renamed"
