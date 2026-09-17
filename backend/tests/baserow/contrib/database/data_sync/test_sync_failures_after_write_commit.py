from unittest.mock import patch

import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.models import SyncDataSyncTableJob
from baserow.core.jobs.constants import JOB_FAILED
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
    return DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_a_non_sync_error_after_the_write_phase_is_recorded_as_last_error(
    data_fixture,
):
    """
    Finding 2. `on_error` used to record `last_error` only for `SyncError`, so a
    RuntimeError, an OperationalError or a worker kill left the data sync reading
    `last_sync=None, last_error=None` -- indistinguishable from a table that was
    never synced -- while its rows sat committed in the table.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    # Fails after `_fetch_and_write_rows` has returned, so its transaction has
    # already committed.
    original = DataSyncHandler._fetch_and_write_rows

    def write_then_boom(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("boom after the rows were committed")

    with patch.object(DataSyncHandler, "_fetch_and_write_rows", write_then_boom):
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )

    rows = data_sync.table.get_model().objects.count()
    assert rows > 0, (
        "this test is vacuous: the write phase committed no rows, so there was "
        "nothing for the failure to leave behind"
    )

    data_sync.refresh_from_db()
    assert data_sync.last_error is not None, (
        f"the sync failed after committing {rows} row(s), but the data sync "
        f"records last_sync={data_sync.last_sync!r} last_error=None, which is "
        f"exactly how a table that was never synced reads"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cancelling_a_sync_does_not_delete_a_table_that_already_has_rows(
    data_fixture,
):
    """
    Finding 3. `on_cancelled` deleted the table whenever `last_sync is None`,
    treating that as "initial sync, nothing written yet". After finding 2 that
    is false: rows can be committed while `last_sync` is still None, and the
    table -- with those rows in it -- was trashed.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    # Put the data sync in the state finding 2 produces: rows committed,
    # `last_sync` still None.
    original = DataSyncHandler._fetch_and_write_rows

    def write_then_boom(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("boom after the rows were committed")

    with patch.object(DataSyncHandler, "_fetch_and_write_rows", write_then_boom):
        with pytest.raises(RuntimeError):
            JobHandler().create_and_start_job(
                user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
            )

    data_sync.refresh_from_db()
    assert data_sync.last_sync is None, (
        "this test no longer reproduces the state it is about: `last_sync` was set"
    )
    rows_before = data_sync.table.get_model().objects.count()
    assert rows_before > 0, "this test is vacuous: no rows were committed"

    job = SyncDataSyncTableJob.objects.filter(data_sync=data_sync).first()
    assert job is not None
    SyncDataSyncTableJobType().on_cancelled(job)

    data_sync.table.refresh_from_db()
    rows_after = data_sync.table.get_model().objects.count()

    assert not data_sync.table.trashed, (
        f"cancelling the sync trashed a table holding {rows_before} committed "
        f"row(s); {rows_after} row(s) remain"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cancelling_an_initial_sync_still_deletes_the_empty_table(data_fixture):
    """
    The complement of the test above: the behaviour that was worth having must
    survive the fix. An initial sync that is cancelled before writing anything
    leaves an empty table the user never asked for, and it is still removed.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    assert data_sync.table.get_model().objects.count() == 0
    assert data_sync.last_sync is None

    # The job is created but never run, which is the state a cancellation before
    # the write phase leaves behind: an empty table and `last_sync is None`.
    job = SyncDataSyncTableJob.objects.create(
        user=user, data_sync=data_sync, state=JOB_FAILED
    )
    SyncDataSyncTableJobType().on_cancelled(job)

    data_sync.table.refresh_from_db()
    assert data_sync.table.trashed, (
        "a cancelled initial sync left an empty, unsynced table behind"
    )
