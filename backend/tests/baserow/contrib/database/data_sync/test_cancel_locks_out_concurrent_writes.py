import threading

from django.db import connection

import psycopg2
import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.models import SyncDataSyncTableJob
from baserow.core.jobs.constants import JOB_FAILED

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


def _make_sync(user, database):
    return DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )


def _second_connection():
    """A genuinely separate connection, so its locks really conflict."""

    params = connection.get_connection_params()
    params.pop("cursor_factory", None)
    return psycopg2.connect(**params)


def _run_while_a_writer_holds_the_table(db_table, fn):
    """
    Holds `ROW EXCLUSIVE` on `db_table` from another connection -- the lock every
    `INSERT`/`UPDATE`/`DELETE` takes -- and runs `fn` against it.

    `SHARE` conflicts with `ROW EXCLUSIVE`, so code that locks the table has to
    wait for this writer to commit; code that doesn't runs straight through.
    Returns whether `fn` was still running when the writer released, which is the
    observable difference between the two.
    """

    holding = threading.Event()
    release = threading.Event()
    fn_done = threading.Event()

    def hold():
        second = _second_connection()
        try:
            with second.cursor() as cursor:
                cursor.execute(f'LOCK TABLE "{db_table}" IN ROW EXCLUSIVE MODE')
                holding.set()
                release.wait(timeout=10)
            second.commit()
        finally:
            second.close()

    thread = threading.Thread(target=hold)
    thread.start()
    assert holding.wait(timeout=5), "the concurrent writer never took its lock"

    result = {}

    def run():
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            result["error"] = exc
        finally:
            fn_done.set()

    fn_thread = threading.Thread(target=run)
    fn_thread.start()

    # If the code under test locks the table, it is still waiting here.
    waited_for_the_writer = not fn_done.wait(timeout=1)

    release.set()
    thread.join(timeout=10)
    fn_thread.join(timeout=10)
    assert not fn_thread.is_alive(), "the code under test never finished"
    if "error" in result:
        raise result["error"]
    return waited_for_the_writer


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_cancelling_a_sync_holds_concurrent_writers_off_while_it_decides(
    data_fixture,
):
    """
    `on_cancelled` checks whether the table is empty and then deletes it. Under
    READ COMMITTED each statement sees a fresh snapshot, so without a lock a sync
    running alongside the cancellation can commit rows between the two and they are
    trashed with the table. The lock has to make the two statements agree.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)
    db_table = data_sync.table.get_model()._meta.db_table

    job = SyncDataSyncTableJob.objects.create(
        user=user, data_sync=data_sync, state=JOB_FAILED
    )

    # A writer holds the table for the whole of `on_cancelled`'s decision, so a
    # cancellation that locks cannot slip between its check and its delete.
    waited = _run_while_a_writer_holds_the_table(
        db_table, lambda: SyncDataSyncTableJobType().on_cancelled(job)
    )

    assert waited, (
        "`on_cancelled` decided whether the table was empty and deleted it while "
        "another connection held a write lock on that table, so a concurrent sync "
        "could commit rows between the two and have them trashed"
    )

    data_sync.table.refresh_from_db()
    assert data_sync.table.trashed, "the empty table was not cleaned up"


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_the_cancel_check_and_the_delete_see_the_same_rows(data_fixture):
    """
    The behaviour the lock exists for, stated without threads: a row committed at
    any point before the cancellation decides must be seen by that decision.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _make_sync(user, database)

    DataSyncHandler().sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.table.get_model().objects.count() == 1

    # A sync wrote rows but never set `last_sync`, which is the state a failure
    # after the write phase leaves behind.
    data_sync.last_sync = None
    data_sync.save()

    job = SyncDataSyncTableJob.objects.create(
        user=user, data_sync=data_sync, state=JOB_FAILED
    )
    SyncDataSyncTableJobType().on_cancelled(job)

    data_sync.table.refresh_from_db()
    assert not data_sync.table.trashed, (
        "the cancellation trashed a table that held a committed row"
    )
