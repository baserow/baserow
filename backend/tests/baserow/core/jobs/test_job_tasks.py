from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.core.cache import cache

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from freezegun import freeze_time
from requests.exceptions import ConnectionError

from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.jobs.models import Job
from baserow.core.jobs.registries import JobType
from baserow.core.jobs.tasks import clean_up_jobs, run_async_job


class TmpCustomJobType(JobType):
    type = "custom_job_type"

    max_count = 1

    model_class = Job

    job_exceptions_map = {
        ConnectionError: "Error message",
    }

    def run(self, job, progress):
        pass


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
@pytest.mark.timeout(10)
def test_run_task(mock_get_by_model, data_fixture):
    data_fixture.register_temp_job_types()

    def run(job, progress):
        progress.increment(50, "test")

        # use job's cached state to determine current state/progress_percentage
        # as this can be updated from another process. A task will not write
        # a job state to db until it's finished correctly.
        assert job.get_cached_state() == "test"
        assert job.get_cached_progress_percentage() == 50

        # We're using the second connection to check if we can get the most recent
        # progress value while the transaction is still active.
        job_copy = Job.objects.using("default-copy").get(pk=job.id)
        # Normal progress is expected to be 0
        assert job_copy.progress_percentage == 0
        assert job_copy.state == JOB_STARTED
        # Progress stored in Redis is expected to be accurate.
        assert job_copy.get_cached_progress_percentage() == 50
        assert job_copy.get_cached_state() == "test"

        progress.increment(50)

    job = data_fixture.create_fake_job()

    # Fake the run method of job
    fake_job_type = TmpCustomJobType()
    fake_job_type.run = Mock(side_effect=run)
    mock_get_by_model.return_value = fake_job_type

    with pytest.raises(Job.DoesNotExist):
        run_async_job(0)

    assert job.state == JOB_PENDING

    run_async_job(job.id)

    fake_job_type.run.assert_called_once()

    job = Job.objects.get(pk=job.id)
    assert job.progress_percentage == 100
    assert job.state == JOB_FINISHED

    # The cache entry will be removed when job completes.
    assert cache.get(job_progress_key(job.id)) is None

    job_copy = Job.objects.using("default-copy").get(pk=job.id)
    assert job_copy.progress_percentage == 100
    assert job_copy.state == JOB_FINISHED
    assert job_copy.get_cached_progress_percentage() == 100
    assert job_copy.get_cached_state() == JOB_FINISHED


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_with_exception(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    job_type.run = Mock(side_effect=Exception("test-1"))
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    with pytest.raises(Exception):
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error == "test-1"
    assert (
        job.human_readable_error
        == "Something went wrong during the custom_job_type job execution."
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_with_sytemexit(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    # Simulate a SystemExit during the run.
    job_type.run = Mock(side_effect=SystemExit(-1))
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    with pytest.raises(SystemExit):
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error == "-1"
    assert (
        job.human_readable_error
        == "Something went wrong during the custom_job_type job execution."
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_failing_time_limit(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    job_type.run = Mock(side_effect=SoftTimeLimitExceeded("test"))
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error == "SoftTimeLimitExceeded('test',)"
    assert (
        job.human_readable_error
        == "The custom_job_type job took too long and was timed out."
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_with_exception_mapping(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    job_type.run = Mock(side_effect=ConnectionError("connection error"))
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error == "connection error"
    assert job.human_readable_error == "Error message"


@pytest.mark.django_db
@patch("baserow.core.storage.get_default_storage")
def test_cleanup_file_import_job(storage_mock, data_fixture, settings):
    now = datetime.now(tz=timezone.utc)
    time_before_expiration = now - timedelta(
        minutes=settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT + 1
    )
    with freeze_time(now):
        data_fixture.create_fake_job()
        data_fixture.create_fake_job(state=JOB_STARTED)
        data_fixture.create_fake_job(state=JOB_FAILED)
        data_fixture.create_fake_job(state=JOB_FINISHED)
        data_fixture.create_fake_job(state="random")

    with freeze_time(time_before_expiration):
        data_fixture.create_fake_job()
        data_fixture.create_fake_job(state=JOB_STARTED)
        data_fixture.create_fake_job(state=JOB_FAILED)
        data_fixture.create_fake_job(state=JOB_FINISHED)
        data_fixture.create_fake_job(state="random")

    assert Job.objects.count() == 10
    assert Job.objects.is_running().count() == 4
    assert Job.objects.is_ended().count() == 4
    assert Job.objects.is_pending_or_running().count() == 6

    # Should keep the job that has just expired as the soft time limit is exceeded
    with freeze_time(now):
        clean_up_jobs()

    assert Job.objects.count() == 8
    assert Job.objects.is_running().count() == 2
    assert Job.objects.is_ended().count() == 5
    assert Job.objects.is_pending_or_running().count() == 3

    # Should delete the job that has been automatically expired by the previous cleanup
    with freeze_time(now):
        clean_up_jobs()

    assert Job.objects.count() == 5
    assert Job.objects.is_running().count() == 2
    assert Job.objects.is_ended().count() == 2
    assert Job.objects.is_pending_or_running().count() == 3
