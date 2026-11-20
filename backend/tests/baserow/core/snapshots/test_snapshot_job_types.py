from datetime import timedelta

from django.conf import settings
from django.utils import timezone

import pytest
from freezegun import freeze_time

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_STARTED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.snapshots.job_types import CreateSnapshotJobType
from baserow.core.snapshots.models import CreateSnapshotJob, Snapshot


@pytest.mark.django_db(transaction=True)
def test_dangling_snapshots_are_removed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)

    snapshot = Snapshot.objects.create(
        snapshot_from_application=database,
        created_by=user,
        name="snapshot",
    )

    with pytest.raises(UserNotInWorkspace):
        job = JobHandler().create_and_start_job(
            user, CreateSnapshotJobType.type, sync=True, snapshot=snapshot
        )
        assert job.state == JOB_FAILED

    # we still keep that snapshot
    assert Snapshot.objects.count() == 1

    assert Snapshot.objects.restorable().count() == 0
    assert Snapshot.objects.unusable().count() == 1

    # cleanup should remove stale snapshots along with a job
    with freeze_time(
        timezone.now()
        + timedelta(minutes=settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT + 10)
    ):
        JobHandler().clean_up_jobs()
    assert Snapshot.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_a_snapshot_cancelled_before_it_is_committed_is_not_created(
    data_fixture, mocker
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    snapshot = Snapshot.objects.create(
        snapshot_from_application=database, created_by=user, name="snapshot"
    )
    real_perform_create = SnapshotHandler.perform_create

    def cancel_once_copied(handler, *args, **kwargs):
        real_perform_create(handler, *args, **kwargs)
        # The user cancels the job after the copy, before it's committed.
        CreateSnapshotJob.objects.filter(snapshot=snapshot).update(state=JOB_CANCELLED)

    mocker.patch.object(
        SnapshotHandler, "perform_create", autospec=True, side_effect=cancel_once_copied
    )

    job = JobHandler().create_and_start_job(
        user, CreateSnapshotJobType.type, sync=True, snapshot=snapshot
    )

    job.refresh_from_db()
    snapshot.refresh_from_db()
    assert job.state == JOB_CANCELLED
    assert snapshot.snapshot_to_application is None


@pytest.mark.django_db
def test_a_created_snapshot_can_no_longer_be_cancelled(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    being_created = Snapshot.objects.create(
        snapshot_from_application=database, created_by=user, name="being created"
    )
    created = data_fixture.create_snapshot(
        snapshot_from_application=database, user=user, name="created"
    )
    being_created_job = CreateSnapshotJob.objects.create(
        user=user, snapshot=being_created, state=JOB_STARTED
    )
    created_job = CreateSnapshotJob.objects.create(
        user=user, snapshot=created, state=JOB_STARTED
    )

    with pytest.raises(JobNotCancellable):
        JobHandler.cancel_job(created_job)

    assert JobHandler.cancel_job(being_created_job).state == JOB_CANCELLED
