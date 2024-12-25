from django.core.cache import cache

import pytest

from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.jobs.models import Job


@pytest.mark.django_db
def test_is_running_queryset(data_fixture):
    data_fixture.create_fake_job(state=JOB_FAILED)
    data_fixture.create_fake_job(state=JOB_FINISHED)
    data_fixture.create_fake_job(state=JOB_PENDING)
    assert Job.objects.is_running().count() == 0

    data_fixture.create_fake_job(state=JOB_STARTED)
    data_fixture.create_fake_job(state="whatever")

    assert Job.objects.is_running().count() == 2


@pytest.mark.django_db
def test_is_finished_queryset(data_fixture):
    data_fixture.create_fake_job(state=JOB_PENDING)
    data_fixture.create_fake_job(state=JOB_STARTED)
    data_fixture.create_fake_job(state="whatever")

    assert Job.objects.is_ended().count() == 0

    data_fixture.create_fake_job(state=JOB_FAILED)
    data_fixture.create_fake_job(state=JOB_FINISHED)

    assert Job.objects.is_ended().count() == 2


@pytest.mark.django_db
def test_is_pending_or_running_queryset(data_fixture):
    data_fixture.create_fake_job(state=JOB_FAILED)
    data_fixture.create_fake_job(state=JOB_FINISHED)

    assert Job.objects.is_pending_or_running().count() == 0

    data_fixture.create_fake_job(state=JOB_PENDING)
    data_fixture.create_fake_job(state=JOB_STARTED)
    data_fixture.create_fake_job(state="whatever")

    assert Job.objects.is_pending_or_running().count() == 3


@pytest.mark.django_db
def test_cached_values(data_fixture):
    job = data_fixture.create_fake_job(
        progress_percentage=10,
        state=JOB_FAILED,
    )

    assert job.progress_percentage == 10
    assert job.state == JOB_FAILED

    assert job.get_cached_progress_percentage() == 10
    assert job.get_cached_state() == JOB_FAILED

    key = job_progress_key(0)
    cache.set(key, {"progress_percentage": 0, "state": "test"})

    assert job.get_cached_progress_percentage() == 10
    assert job.get_cached_state() == JOB_FAILED

    key = job_progress_key(job.id)
    cache.set(key, {"progress_percentage": 20, "state": "something"})

    assert job.get_cached_progress_percentage() == 20
    assert job.get_cached_state() == "something"
