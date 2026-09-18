from unittest.mock import patch

import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import (
    DataSyncSyncedProperty,
)
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.handler import RowHandler
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
LOCATION:Amsterdam
END:VEVENT
END:VCALENDAR"""


def _make_sync(user, database):
    data_sync = DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid"],
        ical_url="https://baserow.io/ical.ics",
    )
    data_sync.auto_add_new_properties = True
    data_sync.save()
    return data_sync


def _fail_after_fetch(data_sync):
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    def failing(self, instance, progress_builder=None):
        list(original(self, instance, progress_builder=progress_builder))
        raise RuntimeError("write phase boom")

    return data_sync_type, original, failing


def _run_failing_sync(user, data_sync, fail_in):
    """
    Runs a sync that fails at `fail_in`, through the real job entry point.

    "fetch" fails once the remote rows have been read but before anything is
    written; "write" lets the fetch succeed and fails inside the write
    transaction instead. They are different code paths -- the second fails with
    a transaction open and rows partly written under it -- and the cleanup has
    to cope with both.
    """

    data_sync_type, original, failing = _fail_after_fetch(data_sync)

    if fail_in == "fetch":
        type(data_sync_type).get_all_rows = failing
        try:
            with pytest.raises(RuntimeError):
                JobHandler().create_and_start_job(
                    user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
                )
        finally:
            type(data_sync_type).get_all_rows = original
    elif fail_in == "write":
        # `create_rows` is called inside the write transaction, after the rows
        # have been fetched and diffed. On a first sync every row is new, so
        # this is the call that carries the write.
        with patch.object(
            RowHandler,
            "create_rows",
            side_effect=RuntimeError("write phase boom"),
        ):
            with pytest.raises(RuntimeError):
                JobHandler().create_and_start_job(
                    user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
                )
    else:
        raise AssertionError(f"unknown failure point {fail_in!r}")


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cleanup_does_not_delete_a_user_created_field(data_fixture):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    user_field_holder = {}
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    def failing(self, instance, progress_builder=None):
        list(original(self, instance, progress_builder=progress_builder))
        # The user adds a field of their own during the sync window.
        user_field_holder["field"] = FieldHandler().create_field(
            user=user,
            table=instance.table,
            type_name="text",
            name="My own notes",
        )
        raise RuntimeError("write phase boom")

    type(data_sync_type).get_all_rows = failing
    try:
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original

    user_field = user_field_holder["field"]
    assert Field.objects.filter(id=user_field.id).exists(), (
        "the failed sync's cleanup deleted a field the user created themselves "
        "during the sync window"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cleanup_failure_leaves_no_orphaned_synced_property(data_fixture):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    data_sync_type, original, failing = _fail_after_fetch(data_sync)

    original_delete_field = FieldHandler.delete_field
    delete_field_calls = []

    def exploding_delete_field(self, *args, **kwargs):
        delete_field_calls.append(args)
        raise RuntimeError("cleanup itself failed")

    type(data_sync_type).get_all_rows = failing
    FieldHandler.delete_field = exploding_delete_field
    try:
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original
        FieldHandler.delete_field = original_delete_field

    # Without this the assertions below are vacuous: a run in which the cleanup
    # never fired also leaves nothing dangling.
    assert delete_field_calls, (
        "the cleanup never attempted to delete a field, so this test never "
        "exercised the failed-cleanup path it is named for"
    )

    props = DataSyncSyncedProperty.objects.filter(data_sync=data_sync)
    dangling = [p.id for p in props if not Field.objects.filter(id=p.field_id).exists()]
    assert dangling == [], (
        f"after a cleanup that failed, {len(dangling)} DataSyncSyncedProperty "
        f"row(s) point at fields that no longer exist: {dangling}"
    )

    # And the data sync must still be usable afterwards.
    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    data_sync.refresh_from_db()
    assert data_sync.last_error is None, (
        f"after a failed cleanup the next sync still errors: {data_sync.last_error}"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cleanup_does_not_delete_fields_a_concurrent_sync_is_using(data_fixture):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    handler = DataSyncHandler()
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    state = {}

    def failing(self, instance, progress_builder=None):
        # Re-entrant: only the OUTER call (sync A) runs the scenario; the nested
        # sync B call falls through to the real implementation.
        if state.get("in_b"):
            return original(self, instance, progress_builder=progress_builder)
        list(original(self, instance, progress_builder=progress_builder))
        state["ran"] = True
        # A second, independent sync of the same data sync completes now, while
        # sync A is between its schema phase and its write phase.
        # In production the fetch routinely takes longer than the sync lock's
        # 2-second TTL (handler.py: `cache.add(lock_key, "locked", timeout=2)`,
        # never refreshed), at which point the lock is gone and a second sync
        # starts. Expire it explicitly rather than sleeping.
        from django.core.cache import cache

        cache.delete(handler.get_table_sync_lock_key(data_sync.id))

        state["in_b"] = True
        try:
            handler.sync_data_sync_table(user=user, data_sync=data_sync)
        finally:
            state["in_b"] = False
        state["rows_after_b"] = instance.table.get_model().objects.count()
        state["fields_after_b"] = set(
            instance.table.field_set.values_list("id", flat=True)
        )
        raise RuntimeError("sync A write phase boom")

    type(data_sync_type).get_all_rows = failing
    try:
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original

    assert state.get("ran"), "the concurrent sync never ran"

    fields_now = set(data_sync.table.field_set.values_list("id", flat=True))
    lost = state["fields_after_b"] - fields_now
    rows_now = data_sync.table.get_model().objects.count()

    assert lost == set(), (
        f"sync A's cleanup deleted {len(lost)} field(s) {sorted(lost)} that the "
        f"successful concurrent sync B had populated; the table went from "
        f"{state['rows_after_b']} row(s) to {rows_now}"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
@pytest.mark.parametrize("fail_in", ["fetch", "write"])
def test_failed_sync_cleanup_actually_calls_delete_field(data_fixture, fail_in):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    with patch.object(
        FieldHandler,
        "delete_field",
        autospec=True,
        side_effect=FieldHandler.delete_field,
    ) as spy:
        _run_failing_sync(user, data_sync, fail_in)

    assert spy.call_count > 0, (
        f"a sync that failed in the {fail_in} phase never deleted any field, so "
        f"the cleanup did not run at all"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch("baserow.contrib.database.data_sync.handler.logger")
def test_cleanup_is_skipped_and_logged_when_another_sync_completed(
    logger_mock, data_fixture
):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    handler = DataSyncHandler()
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    state = {}

    def failing(self, instance, progress_builder=None):
        if state.get("in_b"):
            return original(self, instance, progress_builder=progress_builder)
        list(original(self, instance, progress_builder=progress_builder))
        state["ran"] = True

        from django.core.cache import cache

        cache.delete(handler.get_table_sync_lock_key(data_sync.id))

        state["in_b"] = True
        try:
            handler.sync_data_sync_table(user=user, data_sync=data_sync)
        finally:
            state["in_b"] = False
        raise RuntimeError("sync A write phase boom")

    type(data_sync_type).get_all_rows = failing
    try:
        with patch.object(
            FieldHandler,
            "delete_field",
            autospec=True,
            side_effect=FieldHandler.delete_field,
        ) as spy:
            with pytest.raises(RuntimeError):
                JobHandler().create_and_start_job(
                    user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
                )
    finally:
        type(data_sync_type).get_all_rows = original

    assert state.get("ran"), "the concurrent sync never ran"

    assert spy.call_count == 0, (
        f"sync A's cleanup called delete_field {spy.call_count} time(s) even "
        f"though a concurrent sync had completed successfully in the meantime"
    )
    warnings = " ".join(str(c) for c in logger_mock.warning.call_args_list)
    assert "now contain data" in warnings, (
        f"the cleanup skipped its work without logging why; an operator seeing "
        f"empty columns has nothing to go on. Warnings logged: {warnings!r}"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch("baserow.contrib.database.data_sync.handler.logger")
def test_cleanup_failure_does_not_mask_the_original_error(logger_mock, data_fixture):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    data_sync_type, original, failing = _fail_after_fetch(data_sync)

    def exploding_delete_field(self, *args, **kwargs):
        raise RuntimeError("cleanup itself failed")

    original_delete_field = FieldHandler.delete_field
    type(data_sync_type).get_all_rows = failing
    FieldHandler.delete_field = exploding_delete_field
    try:
        # The ORIGINAL failure must surface, not the cleanup's.
        with pytest.raises(RuntimeError, match="write phase boom"):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original
        FieldHandler.delete_field = original_delete_field

    exceptions = " ".join(str(c) for c in logger_mock.exception.call_args_list)
    assert "Failed to remove the fields added by the failed sync" in exceptions, (
        f"the cleanup swallowed its own exception without logging it, so the "
        f"table can be left with empty columns and no record of why. "
        f"Exceptions logged: {exceptions!r}"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cleanup_does_not_delete_fields_of_a_failed_overlapping_sync(data_fixture):
    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    handler = DataSyncHandler()
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original = type(data_sync_type).get_all_rows

    state = {}

    def failing(self, instance, progress_builder=None):
        if state.get("in_b"):
            return original(self, instance, progress_builder=progress_builder)
        list(original(self, instance, progress_builder=progress_builder))
        state["ran"] = True

        from django.core.cache import cache

        cache.delete(handler.get_table_sync_lock_key(data_sync.id))

        # Sync B writes the rows and then fails, so `last_sync` stays untouched
        # and the old guard sees "nothing changed".
        state["in_b"] = True
        original_write = DataSyncHandler._fetch_and_write_rows

        def write_then_fail(self, *args, **kwargs):
            original_write(self, *args, **kwargs)
            raise RuntimeError("sync B failed after writing")

        try:
            with patch.object(
                DataSyncHandler, "_fetch_and_write_rows", write_then_fail
            ):
                with pytest.raises(RuntimeError):
                    handler.sync_data_sync_table(user=user, data_sync=data_sync)
        finally:
            state["in_b"] = False

        state["rows_after_b"] = instance.table.get_model().objects.count()
        state["fields_after_b"] = set(
            instance.table.field_set.values_list("id", flat=True)
        )
        raise RuntimeError("sync A write phase boom")

    type(data_sync_type).get_all_rows = failing
    try:
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )
    finally:
        type(data_sync_type).get_all_rows = original

    assert state.get("ran"), "the concurrent sync never ran"
    assert state["rows_after_b"] > 0, (
        "this test is vacuous: sync B wrote no rows, so the fields held no data "
        "for the cleanup to destroy"
    )

    data_sync.refresh_from_db()
    assert data_sync.last_sync is None, (
        "this test no longer reproduces the case it is about: `last_sync` moved, "
        "so even the old guard would have skipped the cleanup"
    )

    fields_now = set(data_sync.table.field_set.values_list("id", flat=True))
    lost = state["fields_after_b"] - fields_now
    rows_now = data_sync.table.get_model().objects.count()

    assert lost == set(), (
        f"sync A's cleanup permanently deleted {len(lost)} field(s) "
        f"{sorted(lost)} that the failed concurrent sync B had populated; the "
        f"table went from {state['rows_after_b']} row(s) to {rows_now}"
    )
