import sys
import threading
from time import sleep
from unittest.mock import patch

import pytest

from baserow.core.jobs.constants import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_FINISHED,
    JOB_STARTED,
)
from baserow.core.jobs.exceptions import (
    JobDoesNotExist,
    JobNotCancellable,
    MaxJobCountExceeded,
)
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import Job
from baserow.core.jobs.registries import JobType
from baserow.core.jobs.tasks import run_async_job


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_create_and_start_job(mock_run_async_job, data_fixture):
    data_fixture.register_temp_job_types()

    user = data_fixture.create_user()

    job = JobHandler().create_and_start_job(user, "tmp_job_type_1")
    assert job.user_id == user.id
    assert job.progress_percentage == 0
    assert job.state == "pending"
    assert job.error == ""

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == job.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_create_and_start_job_with_system_exit(mock_run_async_job, data_fixture):
    data_fixture.register_temp_job_types()

    user = data_fixture.create_user()

    # Simulate a SystemExit during the delay call
    mock_run_async_job.delay.side_effect = lambda x: sys.exit(-1)

    with pytest.raises(SystemExit):
        JobHandler().create_and_start_job(user, "tmp_job_type_1")

    job = Job.objects.first()
    assert job.user_id == user.id
    assert job.progress_percentage == 0
    assert job.state == "failed"
    assert job.error == "-1"


@pytest.mark.django_db
def test_exceeding_max_job_count(data_fixture):
    data_fixture.register_temp_job_types()

    user = data_fixture.create_user()

    # Max count is 3 for this job type
    JobHandler().create_and_start_job(user, "tmp_job_type_2")
    JobHandler().create_and_start_job(user, "tmp_job_type_2")
    JobHandler().create_and_start_job(user, "tmp_job_type_2")

    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(user, "tmp_job_type_2")


@pytest.mark.django_db
def test_get_job(data_fixture):
    user = data_fixture.create_user()

    job_1 = data_fixture.create_fake_job(user=user, type="tmp_job_type_1")
    job_2 = data_fixture.create_fake_job(type="tmp_job_type_1")

    with pytest.raises(JobDoesNotExist):
        JobHandler.get_job(user, job_2.id)

    job = JobHandler.get_job(user, job_1.id)
    assert isinstance(job, Job)
    assert job.id == job_1.id


@pytest.mark.django_db
def test_job_progress_changed_bug_regression(data_fixture, mutable_job_type_registry):
    """
    Small regression test for an undefined variable in JobHandler.run
    """

    class IdlingJobType(JobType):
        type = "idling_job"
        model_class = Job

        def run(self, job, progress):
            return (
                job,
                progress,
            )

    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()

    job_1 = data_fixture.create_fake_job(user=user, type=IdlingJobType.type)

    job, progress = JobHandler().run(job_1)

    assert job
    assert progress

    job.progress = 1
    job.save()
    progress.set_progress(1, None)
    assert job.progress == 1
    # in old code this will fail with UnboundLocalError
    progress.set_progress(1, None)


@pytest.mark.django_db()
def test_job_cancel_before_run(data_fixture, mutable_job_type_registry):
    job_started = False

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            nonlocal job_started
            job_started = True

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    job = jh.create_job(user, IdlingJobType.type)
    jh.cancel_job(job)
    jh.run_job(job)

    assert job.cancelled


@pytest.mark.django_db(transaction=True)
def test_job_cancel_when_running(
    data_fixture,
    mutable_job_type_registry,
):
    after_job_cancelled = False
    job_done = False

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            nonlocal after_job_cancelled, job_done
            progress.set_progress(20)

            # No matter who set this in the cache, the next time the job will try to
            # update the progress it will read the state from the cache and stop
            JobHandler().cancel_job(job)
            after_job_cancelled = True

            # Even if we manually reset the job state, the flag in the cache will
            # prevent the job from updating the progress
            job.state = JOB_STARTED
            progress.set_progress(100)
            job_done = True

    jh = JobHandler()

    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)

    job.refresh_from_db()
    assert job.cancelled
    assert job.state == JOB_CANCELLED
    assert job.progress_percentage == 20
    assert after_job_cancelled is True
    assert job_done is False  # set_progress failed to update the progress


@pytest.mark.django_db(transaction=True)
def test_job_cancel_failed(data_fixture, mutable_job_type_registry):
    job_started = False

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            nonlocal job_started
            job_started = True
            JobHandler().cancel_job(job)
            raise ValueError()

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()

    job = jh.create_job(user, IdlingJobType.type)
    with pytest.raises(ValueError):
        jh.schedule_job(job)

    job.refresh_from_db()
    assert job_started is True
    assert job.failed

    with pytest.raises(JobNotCancellable):
        jh.cancel_job(job)

    assert job.failed
    assert job.state == JOB_FAILED


@pytest.mark.django_db()
def test_job_cancel_finished(data_fixture, mutable_job_type_registry):
    job_finished = False

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            nonlocal job_finished
            job_finished = True

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    job = jh.create_and_start_job(user, IdlingJobType.type, sync=True)

    with pytest.raises(JobNotCancellable):
        jh.cancel_job(job)

    assert job_finished is True
    assert job.state == JOB_FINISHED


@pytest.mark.django_db(transaction=True)
def test_job_cancel_cancelled(data_fixture, mutable_job_type_registry):
    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            progress.set_progress(10)
            JobHandler().cancel_job(job)
            progress.set_progress(100)

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)

    job.refresh_from_db()
    assert job.cancelled
    assert job.progress_percentage == 10
    out = JobHandler.cancel_job(job)
    # won't cancel already cancelled
    assert out is None
