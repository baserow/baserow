from django.db import transaction

import pytest
import responses

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.job_types import SyncDataSyncTableJobType
from baserow.contrib.database.data_sync.models import SyncDataSyncTableJob
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
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


def _create_ical_data_sync(data_fixture, user, database):
    return DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="T",
        type_name="ical_calendar",
        synced_properties=["uid", "dtstart", "dtend", "summary"],
        ical_url="https://baserow.io/ical.ics",
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_no_transaction_is_open_while_fetching_rows(data_fixture):
    """
    `get_all_rows` is where the remote HTTP call happens. It must not run inside
    a transaction, otherwise the connection is pinned for the length of the
    fetch -- the problem the fetch/write split exists to solve.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _create_ical_data_sync(data_fixture, user, database)

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_all_rows = type(data_sync_type).get_all_rows
    observed = {}

    def observing_get_all_rows(self, instance, progress_builder=None):
        observed["in_atomic_block"] = transaction.get_connection().in_atomic_block
        return original_get_all_rows(self, instance, progress_builder=progress_builder)

    type(data_sync_type).get_all_rows = observing_get_all_rows
    try:
        JobHandler().create_and_start_job(
            user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
        )
    finally:
        type(data_sync_type).get_all_rows = original_get_all_rows

    assert observed["in_atomic_block"] is False, (
        "a transaction was open while the rows were being fetched from the "
        "remote source, so the connection stays pinned for the whole fetch"
    )


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_no_transaction_is_open_while_reading_properties(data_fixture):
    """
    Some sync types (Hubspot, PostgreSQL) do network I/O in `get_properties`
    too, so it must stay outside the transaction as well. This is why the
    schema phase reads the properties before the write transaction opens and
    only applies them inside it.
    """

    responses.add(responses.GET, "https://baserow.io/ical.ics", status=200, body=FEED)
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = _create_ical_data_sync(data_fixture, user, database)

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    original_get_properties = type(data_sync_type).get_properties
    observed = {}

    def observing_get_properties(self, instance):
        observed.setdefault(
            "in_atomic_block", transaction.get_connection().in_atomic_block
        )
        return original_get_properties(self, instance)

    type(data_sync_type).get_properties = observing_get_properties
    try:
        JobHandler().create_and_start_job(
            user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
        )
    finally:
        type(data_sync_type).get_properties = original_get_properties

    assert observed["in_atomic_block"] is False, (
        "a transaction was open while the sync type's properties were read, "
        "which for some types performs network I/O"
    )


@pytest.mark.django_db(transaction=True)
def test_job_wrapper_does_not_open_a_transaction(data_fixture):
    """
    The job-level wrapper must not open a transaction around the whole run:
    `_do_sync_table` scopes its own transaction to the write phase only.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_sync = data_fixture.create_ical_data_sync(
        user=user,
        table=data_fixture.create_database_table(user=user, database=database),
        ical_url="https://baserow.io/ical.ics",
    )
    job = SyncDataSyncTableJob.objects.create(user=user, data_sync=data_sync)

    with SyncDataSyncTableJobType().transaction_atomic_context(job):
        assert transaction.get_connection().in_atomic_block is False, (
            "the job wrapper opened a transaction that would stay open for the "
            "whole sync, including the remote fetch"
        )
