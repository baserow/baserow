from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.core.cache import cache

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from freezegun import freeze_time
from requests.exceptions import ConnectionError

from baserow.core.job_types import DuplicateApplicationJobType
from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import Job
from baserow.core.jobs.registries import JobType, job_type_registry
from baserow.core.jobs.tasks import clean_up_jobs, run_async_job
from baserow.core.models import DuplicateApplicationJob
from baserow.test_utils.helpers import permanently_delete_workspace


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
    assert job.error_code == ""


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
    assert job.error_code == "SoftTimeLimitExceeded"


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
    assert job.error_code == "ConnectionError"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_calls_on_error_for_mapped_exception(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    exception = ConnectionError("connection error")
    job_type.run = Mock(side_effect=exception)
    job_type.on_error = Mock()
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    run_async_job(job.id)

    job_type.on_error.assert_called_once()
    called_job, called_error = job_type.on_error.call_args.args
    assert called_job.id == job.id
    assert called_error is exception

    job.refresh_from_db()
    assert job.state == JOB_FAILED


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_calls_on_error_for_unmapped_exception(
    mock_get_by_model, data_fixture
):
    job_type = TmpCustomJobType()
    exception = Exception("test-1")
    job_type.run = Mock(side_effect=exception)
    job_type.on_error = Mock()
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    with pytest.raises(Exception):
        run_async_job(job.id)

    job_type.on_error.assert_called_once()


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_run_task_does_not_call_on_error_on_success_or_cancellation(
    mock_get_by_model, data_fixture
):
    job_type = TmpCustomJobType()
    job_type.run = Mock()
    job_type.on_error = Mock()
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()
    run_async_job(job.id)
    job_type.on_error.assert_not_called()

    cancelled_job = data_fixture.create_fake_job()
    JobHandler.cancel_job(cancelled_job)
    run_async_job(cancelled_job.id)
    job_type.on_error.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_on_error_runs_after_failed_state_is_saved(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    job_type.run = Mock(side_effect=ConnectionError("connection error"))

    def on_error(failed_job, error):
        Job.objects.filter(id=failed_job.id).update(
            human_readable_error="from-on-error"
        )

    job_type.on_error = Mock(side_effect=on_error)
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    run_async_job(job.id)

    # A hook running before the failure save would be overwritten by it.
    job.refresh_from_db()
    assert job.human_readable_error == "from-on-error"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.registries.JobTypeRegistry.get_by_model")
def test_on_error_exception_does_not_mask_job_failure(mock_get_by_model, data_fixture):
    job_type = TmpCustomJobType()
    job_type.run = Mock(side_effect=ConnectionError("connection error"))
    job_type.on_error = Mock(side_effect=RuntimeError("hook broke"))
    mock_get_by_model.return_value = job_type

    job = data_fixture.create_fake_job()

    run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.human_readable_error == "Error message"


class WorkFailed(Exception):
    pass


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "work_error,state",
    [(None, JOB_FINISHED), (WorkFailed, JOB_FAILED), (JobCancelled, JOB_CANCELLED)],
)
def test_job_ends_when_related_objects_deleted_during_run(
    data_fixture, monkeypatch, work_error, state
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    job_type = job_type_registry.get(DuplicateApplicationJobType.type)
    run_in_transaction = job_type.transaction_atomic_context

    @contextmanager
    def delete_workspace_when_transaction_ends(job):
        try:
            with run_in_transaction(job):
                yield
        finally:
            permanently_delete_workspace(workspace)

    monkeypatch.setattr(
        job_type, "transaction_atomic_context", delete_workspace_when_transaction_ends
    )
    monkeypatch.setattr(job_type, "on_error", Mock())
    if work_error:
        monkeypatch.setattr(job_type, "run", Mock(side_effect=work_error()))
    if work_error is WorkFailed:
        with pytest.raises(WorkFailed):
            JobHandler().create_and_start_job(
                user, job_type.type, application_id=application.id, sync=True
            )
    else:
        JobHandler().create_and_start_job(
            user, job_type.type, application_id=application.id, sync=True
        )

    job = DuplicateApplicationJob.objects.get(user=user)
    assert job.state == state
    assert job.original_application_id is None
    assert job.duplicated_application_id is None
    assert job_type.on_error.call_count == (1 if state == JOB_FAILED else 0)


@pytest.mark.django_db(transaction=True)
def test_job_ends_when_relation_deleted_after_check(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    unset_relations = JobHandler.unset_relations_to_deleted_objects
    deleted = []

    def unset_relations_then_delete_workspace(job):
        result = unset_relations(job)
        if job.state == JOB_FINISHED and not deleted:
            permanently_delete_workspace(workspace)
            deleted.append(workspace.id)
        return result

    monkeypatch.setattr(
        JobHandler,
        "unset_relations_to_deleted_objects",
        staticmethod(unset_relations_then_delete_workspace),
    )

    JobHandler().create_and_start_job(
        user, DuplicateApplicationJobType.type, application_id=application.id, sync=True
    )

    job = DuplicateApplicationJob.objects.get(user=user)
    assert deleted == [workspace.id]
    assert job.state == JOB_FINISHED
    assert job.original_application_id is None
    assert job.duplicated_application_id is None


@pytest.mark.django_db(transaction=True)
def test_job_cancelled_after_its_work_ends_stays_cancelled(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    application = data_fixture.create_database_application(user=user)
    job_type = job_type_registry.get(DuplicateApplicationJobType.type)
    run_in_transaction = job_type.transaction_atomic_context

    @contextmanager
    def cancel_when_transaction_ends(job):
        with run_in_transaction(job):
            yield
        JobHandler.cancel_job(Job.objects.get(id=job.id))

    monkeypatch.setattr(
        job_type, "transaction_atomic_context", cancel_when_transaction_ends
    )
    monkeypatch.setattr(job_type, "on_cancelled", Mock())

    JobHandler().create_and_start_job(
        user, job_type.type, application_id=application.id, sync=True
    )

    assert DuplicateApplicationJob.objects.get(user=user).state == JOB_CANCELLED
    job_type.on_cancelled.assert_called_once()


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

    expired_jobs = Job.objects.filter(error="Timeout error")
    assert expired_jobs.count() > 0
    assert all(job.error_code == "SoftTimeLimitExceeded" for job in expired_jobs)

    # Should delete the job that has been automatically expired by the previous cleanup
    with freeze_time(now):
        clean_up_jobs()

    assert Job.objects.count() == 5
    assert Job.objects.is_running().count() == 2
    assert Job.objects.is_ended().count() == 2
    assert Job.objects.is_pending_or_running().count() == 3
