import threading
from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APIClient

from baserow.core.models import Template
from baserow.core.user_templates.job_types import DownloadUserTemplateJobType
from baserow.core.user_templates.models import DownloadUserTemplateJob
from tests.baserow.core.user_templates.utils import create_template, queued

pytestmark = pytest.mark.django_db

JOBS_URL = reverse("api:jobs:list")


def request_download(api_client, token, template, latest=False):
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.post(
        JOBS_URL,
        {
            "type": DownloadUserTemplateJobType.type,
            "slug": template.slug,
            "latest": latest,
        },
        format="json",
        **headers,
    )


@pytest.mark.parametrize(
    "actor,state,latest,status,error",
    [
        ("owner", "private", False, HTTP_200_OK, None),
        (
            "other",
            "private",
            False,
            HTTP_404_NOT_FOUND,
            "ERROR_TEMPLATE_DOES_NOT_EXIST",
        ),
        ("other", "public", True, HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        ("owner", "blocked", False, HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_BLOCKED"),
        ("owner", "no_content", False, 400, "ERROR_TEMPLATE_HAS_NO_CONTENT"),
    ],
)
def test_download_user_template(
    api_client, data_fixture, actor, state, latest, status, error
):
    owner, owner_token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    if state == "no_content":
        Template.objects.filter(id=template.id).update(pruned_at=timezone.now())
    else:
        data_fixture.set_user_template_state(template, state)
    token = owner_token if actor == "owner" else data_fixture.create_user_and_token()[1]

    response = request_download(api_client, token, template, latest)

    assert response.status_code == status, response.json()
    if error:
        assert response.json()["error"] == error
        assert not DownloadUserTemplateJob.objects.exists()
    else:
        assert response.json()["type"] == DownloadUserTemplateJobType.type


def test_download_user_template_signed_out(api_client, data_fixture):
    template = create_template(data_fixture, data_fixture.create_user())
    data_fixture.set_user_template_state(template, "public")

    response = request_download(api_client, None, template)

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
def test_download_user_template_at_the_same_time_gets_one_job(data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    data_fixture.set_user_template_state(template, "public")
    first_checked = threading.Event()
    release = threading.Event()
    can_schedule_or_raise = DownloadUserTemplateJobType.can_schedule_or_raise
    responses = {}
    errors = []

    # The first request pauses after it found no job to attach to, before it
    # commits its own job.
    def pause_the_first_request(job_type, job):
        if not first_checked.is_set():
            first_checked.set()
            release.wait(timeout=10)
        return can_schedule_or_raise(job_type, job)

    def in_thread(name, token):
        def run():
            try:
                responses[name] = request_download(APIClient(), token, template)
            except Exception as error:
                errors.append(error)
            finally:
                connection.close()

        thread = threading.Thread(target=run)
        thread.start()
        return thread

    with (
        queued(),
        patch.object(
            DownloadUserTemplateJobType,
            "can_schedule_or_raise",
            pause_the_first_request,
        ),
    ):
        first = in_thread("first", owner_token)
        try:
            assert first_checked.wait(timeout=10)
            second = in_thread("second", token)
            second.join(timeout=1)
            second_waited = second.is_alive()
        finally:
            release.set()
            first.join(timeout=10)
        second.join(timeout=10)

    assert errors == []
    # The second request waited for the revision the first one locked.
    assert second_waited
    assert responses["first"].status_code == HTTP_200_OK, responses["first"].json()
    assert responses["second"].status_code == HTTP_200_OK, responses["second"].json()
    assert responses["second"].json()["id"] == responses["first"].json()["id"]
    assert DownloadUserTemplateJob.objects.count() == 1
