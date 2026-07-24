from datetime import timedelta

from django.utils import timezone

import pytest
import responses

from baserow.contrib.database.data_sync.models import (
    DATA_SYNC_JOB_TRIGGERED_BY_MANUAL,
    DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    SyncDataSyncTableJob,
)
from baserow.contrib.database.table.signals import table_updated
from baserow.core.jobs.constants import JOB_FAILED
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_failed_sync_persists_last_error_and_broadcasts_table_updated(data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body="",
    )

    user = data_fixture.create_user()
    data_sync = data_fixture.create_ical_data_sync(
        user=user, ical_url="https://baserow.io/ical.ics"
    )

    updated_table_ids = []

    def receiver(sender, table, **kwargs):
        updated_table_ids.append(table.id)

    table_updated.connect(receiver)
    try:
        job = JobHandler().create_and_start_job(
            user, "sync_data_sync_table", sync=True, data_sync_id=data_sync.id
        )
    finally:
        table_updated.disconnect(receiver)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.triggered_by == DATA_SYNC_JOB_TRIGGERED_BY_MANUAL

    # The sync transaction rolled back, but on_error must persist the error.
    data_sync.refresh_from_db()
    assert (
        data_sync.last_error
        == "The request to the URL didn't respond with an OK response code."
    )
    assert data_sync.table_id in updated_table_ids


@pytest.mark.django_db
def test_cannot_start_sync_when_another_users_sync_is_running(data_fixture):
    user_1 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user_1)
    user_2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_sync = data_fixture.create_ical_data_sync(
        table=table, ical_url="https://baserow.io/ical.ics"
    )

    SyncDataSyncTableJob.objects.create(user=user_2, data_sync=data_sync)

    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user_1, "sync_data_sync_table", data_sync_id=data_sync.id
        )


@pytest.mark.django_db
def test_periodic_runs_bypass_the_per_user_max_count(data_fixture):
    user = data_fixture.create_user()
    job_type = job_type_registry.get("sync_data_sync_table")

    for _ in range(job_type.max_count):
        data_sync = data_fixture.create_ical_data_sync(
            user=user, ical_url="https://baserow.io/ical.ics"
        )
        SyncDataSyncTableJob.objects.create(user=user, data_sync=data_sync)

    new_data_sync = data_fixture.create_ical_data_sync(
        user=user, ical_url="https://baserow.io/ical.ics"
    )

    manual_job = SyncDataSyncTableJob(
        user=user,
        data_sync=new_data_sync,
        triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_MANUAL,
    )
    with pytest.raises(MaxJobCountExceeded):
        job_type.can_schedule_or_raise(manual_job)

    periodic_job = SyncDataSyncTableJob(
        user=user,
        data_sync=new_data_sync,
        triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    )
    job_type.can_schedule_or_raise(periodic_job)


@pytest.mark.django_db
def test_stale_job_rows_do_not_block_new_syncs(data_fixture, settings):
    user = data_fixture.create_user()
    data_sync = data_fixture.create_ical_data_sync(
        user=user, ical_url="https://baserow.io/ical.ics"
    )
    stale_job = SyncDataSyncTableJob.objects.create(user=user, data_sync=data_sync)
    SyncDataSyncTableJob.objects.filter(id=stale_job.id).update(
        updated_on=timezone.now()
        - timedelta(seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 1)
    )

    job_type = job_type_registry.get("sync_data_sync_table")
    job_type.can_schedule_or_raise(SyncDataSyncTableJob(user=user, data_sync=data_sync))


@pytest.mark.django_db
def test_periodic_runs_do_not_consume_the_users_manual_cap(data_fixture):
    user = data_fixture.create_user()
    job_type = job_type_registry.get("sync_data_sync_table")

    for _ in range(job_type.max_count):
        data_sync = data_fixture.create_ical_data_sync(
            user=user, ical_url="https://baserow.io/ical.ics"
        )
        SyncDataSyncTableJob.objects.create(
            user=user,
            data_sync=data_sync,
            triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
        )

    new_data_sync = data_fixture.create_ical_data_sync(
        user=user, ical_url="https://baserow.io/ical.ics"
    )
    job_type.can_schedule_or_raise(
        SyncDataSyncTableJob(
            user=user,
            data_sync=new_data_sync,
            triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_MANUAL,
        )
    )
