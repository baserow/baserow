from django.shortcuts import reverse
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import Template
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.job_types import DownloadUserTemplateJobType
from baserow.core.user_templates.models import DownloadUserTemplateJob
from tests.baserow.core.user_templates.utils import (
    create_template,
    store_template_archive,
)

pytestmark = pytest.mark.django_db


def request_download(api_client, token, template, latest=False):
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.post(
        reverse("api:templates:download", kwargs={"slug": template.slug}),
        {"latest": latest},
        format="json",
        **headers,
    )


@pytest.mark.parametrize(
    "actor,state,latest,status,error",
    [
        ("owner", "private", False, HTTP_202_ACCEPTED, None),
        ("owner", "private", True, HTTP_202_ACCEPTED, None),
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
def test_download_user_template_without_archive(
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
        # The job builds the archive, which is asked for again once it's finished.
        job = response.json()
        assert job["type"] == DownloadUserTemplateJobType.type
        assert (job["slug"], job["latest"]) == (template.slug, latest)
        assert DownloadUserTemplateJob.objects.get(id=job["id"]).revision_id == (
            template.id
        )


@pytest.mark.usefixtures("use_tmp_media_root")
@pytest.mark.parametrize(
    "name,file_name",
    [("Sales pipeline", "sales-pipeline.zip"), ("!!!", "template.zip")],
)
def test_download_user_template_with_archive(api_client, data_fixture, name, file_name):
    owner, token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    Template.objects.filter(id=template.id).update(name=name)
    archive = store_template_archive(template)

    response = request_download(api_client, token, template)

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == {
        "url": get_default_storage().url(archive),
        "file_name": file_name,
    }
    assert not DownloadUserTemplateJob.objects.exists()


@pytest.mark.usefixtures("use_tmp_media_root")
def test_download_user_template_with_archive_needs_access(api_client, data_fixture):
    template = create_template(data_fixture, data_fixture.create_user())
    data_fixture.set_user_template_state(template, "private")
    store_template_archive(template)
    _, token = data_fixture.create_user_and_token()

    response = request_download(api_client, token, template)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"


def test_download_user_template_reuses_the_running_job(api_client, data_fixture):
    owner, token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    other = create_template(data_fixture, owner)

    first = request_download(api_client, token, template)
    second = request_download(api_client, token, template, latest=True)

    assert (first.status_code, second.status_code) == (202, 202)
    assert first.json()["id"] == second.json()["id"]
    # One download job at a time.
    response = request_download(api_client, token, other)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAX_JOB_COUNT_EXCEEDED"


def test_download_user_template_starts_a_job_of_its_own(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    user, token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    data_fixture.set_user_template_state(template, "public")
    owner_job = request_download(api_client, owner_token, template)
    ended = DownloadUserTemplateJob.objects.create(
        user=user, revision=template, state=JOB_FINISHED
    )

    response = request_download(api_client, token, template)

    assert response.status_code == HTTP_202_ACCEPTED
    assert response.json()["id"] not in (owner_job.json()["id"], ended.id)


def test_download_user_template_signed_out(api_client, data_fixture):
    template = create_template(data_fixture, data_fixture.create_user())
    data_fixture.set_user_template_state(template, "public")

    response = request_download(api_client, None, template)

    assert response.status_code == HTTP_401_UNAUTHORIZED
