import sys
import threading
from time import sleep
from unittest.mock import patch

import pytest

from baserow.core.jobs.constants import JOB_CANCELLED
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_job_cancel_before_run(data_fixture, test_thread, mutable_job_type_registry):
    # marker that the job started
    m_start = threading.Event()

    # marker for job to stop
    m_set_stop = threading.Event()

    # marker that job finished
    m_end = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            m_start.set()
            m_set_stop.wait(0.5)
            progress.set_progress(10)
            m_end.set()

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)
    assert job.user_id == user.id
    assert job.get_cached_progress_percentage() == 0
    assert job.pending
    assert job.error == ""
    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending
        assert job.progress_percentage == 0
        jh.cancel_job(job)
        t.start()
        sleep(0.005)
        # Job.run should not be called so markers are not set
        assert not m_start.is_set()
        assert not m_end.is_set()

    job.refresh_from_db()
    assert job.cancelled, (
        job.get_cached_state(),
        job.state,
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_job_cancel_when_running(data_fixture, test_thread, mutable_job_type_registry):
    # marker that the job started
    m_start = threading.Event()

    # marker for job to stop
    m_set_stop = threading.Event()

    # marker that job finished
    m_end = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            progress.set_progress(11)
            m_start.set()
            progress.set_progress(11)
            assert m_set_stop.wait(0.5)
            progress.set_progress(12)
            m_end.set()

    jh = JobHandler()

    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)
    assert job.user_id == user.id
    assert job.get_cached_progress_percentage() == 0
    assert job.pending
    assert job.error == ""
    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending
        assert job.get_cached_progress_percentage() == 0

        t.start()
        assert m_start.wait(0.5)
        assert job.started, job.get_cached_state()
        assert (
            job.get_cached_progress_percentage() == 11
        ), job.get_cached_progress_percentage()

        jh.cancel_job(job)
        m_set_stop.set()
        assert not m_end.wait(0.5)

    job.refresh_from_db()
    # progress percentage is set from model's state, not from cache,
    # so this is a different value than one set from .run method
    assert job.cancelled
    assert job.state == JOB_CANCELLED


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_job_cancel_failed(data_fixture, test_thread, mutable_job_type_registry):
    # marker that the job started
    m_start = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            m_start.set()
            raise ValueError()

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)
    assert job.user_id == user.id
    assert job.get_cached_progress_percentage() == 0
    assert job.pending
    assert job.error == ""
    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending
        assert job.get_cached_progress_percentage() == 0

        t.start()
        assert t.is_alive()
        assert m_start.wait(0.5)

    # a job failed, so we can't cancel it
    job.refresh_from_db()
    assert job.failed
    with pytest.raises(JobNotCancellable):
        jh.cancel_job(job)
    job.refresh_from_db()
    assert job.failed


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_job_cancel_finished(data_fixture, test_thread, mutable_job_type_registry):
    m_start = threading.Event()
    m_set_stop = threading.Event()
    m_end = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            m_start.set()
            assert m_set_stop.wait(0.5)
            m_end.set()

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)
    assert job.user_id == user.id
    assert job.get_cached_progress_percentage() == 0
    assert job.pending
    assert job.error == ""
    with test_thread(run_async_job, job.id) as t:
        assert job.pending
        assert job.get_cached_progress_percentage() == 0

        t.start()
        assert t.is_alive()
        assert m_start.wait(0.5)
        m_set_stop.set()
        assert m_end.wait(0.5)

    job.refresh_from_db()
    with pytest.raises(JobNotCancellable):
        assert job.finished, job.get_cached_state()
        jh.cancel_job(job)


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_job_cancel_cancelled(data_fixture, test_thread, mutable_job_type_registry):
    m_start = threading.Event()
    m_set_stop = threading.Event()
    m_end = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            m_start.set()
            progress.set_progress(10)
            assert m_set_stop.wait(0.5)
            progress.set_progress(20)
            m_end.set()
            progress.set_progress(30)

    jh = JobHandler()
    mutable_job_type_registry.register(IdlingJobType())

    user = data_fixture.create_user()
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = jh.create_and_start_job(user, IdlingJobType.type, sync=False)
    assert job.user_id == user.id
    assert job.get_cached_progress_percentage() == 0
    assert job.pending
    assert job.error == ""
    with test_thread(run_async_job, job.id) as t:
        assert job.pending
        assert job.get_cached_progress_percentage() == 0

        t.start()
        assert t.is_alive()
        assert m_start.wait(0.5)
        out = JobHandler.cancel_job(job)
        assert isinstance(out, Job)
        m_set_stop.set()

    job.refresh_from_db()
    assert job.cancelled, job.state
    out = JobHandler.cancel_job(job)
    # won't cancel already cancelled
    assert out is None
