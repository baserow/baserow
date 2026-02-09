import threading
from unittest.mock import patch

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.core.jobs.constants import JOB_CANCELLED
from baserow.core.jobs.models import Job
from baserow.core.jobs.registries import JobType
from baserow.core.jobs.tasks import run_async_job
from baserow.test_utils.helpers import is_dict_subset


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_create_job(mock_run_async, data_fixture, api_client):
    data_fixture.register_temp_job_types()

    user = data_fixture.create_user()

    run_time = "2023-01-01T12:00:00Z"
    with freeze_time("2023-01-01 12:00:00"):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            reverse("api:jobs:list"),
            {},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert response.json() == {
            "error": "ERROR_REQUEST_BODY_VALIDATION",
            "detail": {
                "type": [{"error": "This field is required.", "code": "required"}],
            },
        }

        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": "tmp_job_type_1",
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert response.json() == {
            "error": "ERROR_REQUEST_BODY_VALIDATION",
            "detail": {
                "test_request_field": [
                    {"error": "This field is required.", "code": "required"}
                ],
            },
        }

        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": "tmp_job_type_1",
                "test_request_field": "test",
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert response.json() == {
            "error": "ERROR_REQUEST_BODY_VALIDATION",
            "detail": {
                "test_request_field": [
                    {"error": "A valid integer is required.", "code": "invalid"}
                ],
            },
        }

        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": "tmp_job_type_3",
                "test_request_field": 1,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["error"] == "TEST_EXCEPTION"

        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": "tmp_job_type_1",
                "test_request_field": 1,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        job = Job.objects.all().first()

        assert response.json() == {
            "id": job.id,
            "created_on": run_time,
            "updated_on": run_time,
            "type": "tmp_job_type_1",
            "test_field": 42,
            "state": "pending",
            "progress_percentage": 0,
            "human_readable_error": "",
        }
        mock_run_async.delay.assert_called()

        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": "tmp_job_type_1",
                "test_request_field": 1,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_MAX_JOB_COUNT_EXCEEDED"


@pytest.mark.django_db
def test_list_jobs(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()

    with freeze_time("2023-01-01 12:00:00"):
        job_1 = data_fixture.create_fake_job(user=user)
        job_2 = data_fixture.create_fake_job(user=user, state="failed")
        job_3 = data_fixture.create_fake_job()

    url = reverse("api:jobs:list")

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    job_1_json = {
        "id": job_1.id,
        "created_on": "2023-01-01T12:00:00Z",
        "updated_on": "2023-01-01T12:00:00Z",
        "type": "tmp_job_type_1",
        "progress_percentage": 0,
        "state": "pending",
        "human_readable_error": "",
        "test_field": 42,
    }

    job_2_json = {
        "id": job_2.id,
        "type": "tmp_job_type_1",
        "created_on": "2023-01-01T12:00:00Z",
        "updated_on": "2023-01-01T12:00:00Z",
        "progress_percentage": 0,
        "state": "failed",
        "human_readable_error": "",
        "test_field": 42,
    }

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"jobs": [job_2_json, job_1_json]}

    valid_job_states = ",".join(["pending", "finished"])
    response = api_client.get(
        f"{url}?states={valid_job_states}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"jobs": [job_1_json]}

    response = api_client.get(
        f"{url}?states=!finished",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"jobs": [job_2_json, job_1_json]}

    response = api_client.get(
        f"{url}?states=importing",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json() == {
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
        "detail": {
            "states": [
                {
                    "error": "State importing is not a valid state. "
                    "Valid states are: pending, finished, failed, "
                    "cancelled.",
                    "code": "invalid",
                }
            ],
        },
    }

    response = api_client.get(
        f"{url}?job_ids={job_2.id},{job_3.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"jobs": [job_2_json]}

    response = api_client.get(
        f"{url}?job_ids=invalid_job_id",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json() == {
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
        "detail": {
            "job_ids": [
                {
                    "error": "Job id invalid_job_id is not a valid integer.",
                    "code": "invalid",
                }
            ],
        },
    }


@pytest.mark.django_db
@patch("baserow.core.jobs.handler.run_async_job")
def test_list_jobs_with_type_specific_filters(mock_run_async, data_fixture, api_client):
    """Test that type-specific filters work correctly and are isolated per job type."""

    data_fixture.register_temp_job_types()
    user, token = data_fixture.create_user_and_token()
    job = data_fixture.create_fake_job(user=user, type="tmp_job_type_1")

    response = api_client.get(
        reverse("api:jobs:list"),
        {
            "non_existing_field": "will_be_ignored",
            "type": "tmp_job_type_1",
            "test_request_field": 1,
            "tmp_job_type_1_progress_percentage": 100,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["jobs"]) == 0

    response = api_client.get(
        reverse("api:jobs:list"),
        {
            "type": "tmp_job_type_1",
            "test_request_field": 1,
            "tmp_job_type_1_progress_percentage": 0,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert len(response.json()["jobs"]) == 1
    assert response.json()["jobs"][0]["id"] == job.id


@pytest.mark.django_db
def test_get_job(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()

    run_time = "2023-01-01T12:00:00Z"
    with freeze_time("2023-01-01 12:00:00"):
        job_1 = data_fixture.create_fake_job(user=user)
        job_2 = data_fixture.create_fake_job()

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job_2.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_JOB_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job_1.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    json = response.json()

    assert json == {
        "id": job_1.id,
        "created_on": run_time,
        "updated_on": run_time,
        "type": "tmp_job_type_1",
        "progress_percentage": 0,
        "state": "pending",
        "human_readable_error": "",
        "test_field": 42,
    }

    updated_time = "2023-01-01T13:00:00Z"
    with freeze_time("2023-01-01 13:00:00"):
        job_1.progress_percentage = 50
        job_1.state = "failed"
        job_1.human_readable_error = "Wrong"
        job_1.save()

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job_1.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    json = response.json()

    assert json == {
        "id": job_1.id,
        "created_on": run_time,
        "updated_on": updated_time,
        "type": "tmp_job_type_1",
        "progress_percentage": 50,
        "state": "failed",
        "human_readable_error": "Wrong",
        "test_field": 42,
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_cancel_job_running(
    data_fixture, api_client, test_thread, mutable_job_type_registry
):
    # marker that the job started
    m_start = threading.Event()

    # marker for job to stop
    m_set_stop = threading.Event()
    # confirmation of m_set_stop
    m_stop_wait = threading.Event()

    # marker that job finished
    m_end = threading.Event()

    class IdlingJobType(JobType):
        type = "idling_job_b"
        model_class = Job
        max_count = 1

        def run(self, job, progress):
            m_start.set()
            progress.set_progress(1)
            assert m_set_stop.wait(2)
            progress.set_progress(2)
            m_end.set()
            progress.set_progress(3)

    mutable_job_type_registry.register(IdlingJobType())

    user, token = data_fixture.create_user_and_token()

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": IdlingJobType.type,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    resp = response.json()
    job = Job.objects.get(id=resp["id"]).specific

    assert job
    assert job.id
    assert job.specific
    assert is_dict_subset(
        {
            "id": job.id,
            "type": IdlingJobType.type,
            "state": "pending",
            "progress_percentage": 0,
            "human_readable_error": "",
        },
        resp,
    )

    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending, job.get_cached_state()
        t.start()
        assert m_start.wait(0.5)
        assert job.started, job.get_cached_state()

        response = api_client.post(
            reverse("api:jobs:cancel", args=(job.id,)),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        resp = response.json()
        assert is_dict_subset(
            {"state": "cancelled", "id": job.id, "type": IdlingJobType.type}, resp
        )
        m_set_stop.set()

        assert t.thread_stopped.wait(2)
        job.refresh_from_db()
        assert job.cancelled, job.get_cached_state()

    assert not m_end.is_set()
    assert response.status_code == HTTP_200_OK

    job_data = response.json()
    assert job_data["state"] == JOB_CANCELLED


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_cancel_job_pending(
    data_fixture, api_client, test_thread, mutable_job_type_registry
):
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
            progress.set_progress(1)
            assert m_set_stop.wait(1)
            progress.set_progress(2)
            m_end.set()

    mutable_job_type_registry.register(IdlingJobType())

    user, token = data_fixture.create_user_and_token()

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": IdlingJobType.type,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    resp = response.json()
    job = Job.objects.get(id=resp["id"]).specific

    assert job
    assert job.id
    assert job.specific
    assert is_dict_subset(
        {
            "id": job.id,
            "type": IdlingJobType.type,
            "state": "pending",
            "progress_percentage": 0,
            "human_readable_error": "",
        },
        resp,
    )

    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending, job.get_cached_state()
        response = api_client.post(
            reverse("api:jobs:cancel", args=(job.id,)),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        t.start()
        assert job.cancelled, job.get_cached_state()

    assert not m_start.is_set()
    assert not m_end.is_set()
    job_data = response.json()
    assert job_data["state"] == JOB_CANCELLED


@pytest.mark.django_db(transaction=True)
@pytest.mark.flaky(retries=3, delay=1)
def test_cancel_job_finished(
    data_fixture, api_client, test_thread, mutable_job_type_registry
):
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
            progress.set_progress(1)
            assert m_set_stop.wait(1)
            progress.set_progress(2)
            m_end.set()

    mutable_job_type_registry.register(IdlingJobType())

    user, token = data_fixture.create_user_and_token()

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        response = api_client.post(
            reverse("api:jobs:list"),
            {
                "type": IdlingJobType.type,
            },
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    resp = response.json()
    job = Job.objects.get(id=resp["id"]).specific

    assert job
    assert job.id
    assert job.specific
    assert is_dict_subset(
        {
            "id": job.id,
            "type": IdlingJobType.type,
            "state": "pending",
            "progress_percentage": 0,
            "human_readable_error": "",
        },
        resp,
    )

    with test_thread(run_async_job.apply, args=(job.id,)) as t:
        assert job.pending, job.get_cached_state()

        t.start()
        assert m_start.wait(0.5)
        m_set_stop.set()
        assert m_end.wait(0.5)

        response = api_client.post(
            reverse("api:jobs:cancel", args=(job.id,)),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_400_BAD_REQUEST
    resp = response.json()
    assert resp.get("error") == "ERROR_JOB_NOT_CANCELLABLE"
