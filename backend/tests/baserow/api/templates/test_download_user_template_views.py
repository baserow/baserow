from django.shortcuts import reverse

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


def request_download(api_client, token, template, revision_id="shown"):
    """Asks for the archive of the template's root, as the revision shown."""

    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    if revision_id == "shown":
        revision_id = template.id
    return api_client.post(
        reverse("api:templates:download", kwargs={"slug": template.slug}),
        {} if revision_id is None else {"revision_id": revision_id},
        format="json",
        **headers,
    )


@pytest.mark.parametrize(
    "actor,revisions,status,error",
    [
        ("owner", ["private"], HTTP_202_ACCEPTED, None),
        ("other", ["public"], HTTP_202_ACCEPTED, None),
        ("other", ["private"], HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        # Another revision was made public since the template was shown.
        ("other", ["private", "public"], 400, "ERROR_TEMPLATE_UPDATED"),
        ("owner", ["blocked"], HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_BLOCKED"),
        ("owner", ["pruned"], 400, "ERROR_TEMPLATE_HAS_NO_CONTENT"),
        # Without the id of the revision shown.
        ("owner", None, 400, "ERROR_REQUEST_BODY_VALIDATION"),
    ],
)
def test_download_user_template_without_archive(
    api_client, data_fixture, actor, revisions, status, error
):
    owner, owner_token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner)
    data_fixture.set_user_template_revision_states(template, revisions or [])
    revision_id = "shown" if revisions else None
    token = owner_token if actor == "owner" else data_fixture.create_user_and_token()[1]

    response = request_download(api_client, token, template, revision_id)

    assert response.status_code == status, response.json()
    if error:
        assert response.json()["error"] == error
        assert not DownloadUserTemplateJob.objects.exists()
    else:
        # The job builds the archive, which is asked for again once it's finished.
        job = response.json()
        assert job["type"] == DownloadUserTemplateJobType.type
        assert (job["slug"], job["revision_id"], job["template_name"]) == (
            template.slug,
            template.id,
            template.name,
        )
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
    second = request_download(api_client, token, template)

    assert (first.status_code, second.status_code) == (202, 202)
    assert first.json()["id"] == second.json()["id"]
    # One download job at a time.
    response = request_download(api_client, token, other)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAX_JOB_COUNT_EXCEEDED"


def test_download_user_template_starts_a_job_of_its_own(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    user, token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, owner, "public")
    owner_job = request_download(api_client, owner_token, template)
    ended = DownloadUserTemplateJob.objects.create(
        user=user, revision=template, state=JOB_FINISHED
    )

    response = request_download(api_client, token, template)

    assert response.status_code == HTTP_202_ACCEPTED
    assert response.json()["id"] not in (owner_job.json()["id"], ended.id)


def test_download_user_template_signed_out(api_client, data_fixture):
    template = create_template(data_fixture, data_fixture.create_user(), "public")

    response = request_download(api_client, None, template)

    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_jobs_endpoint_refuses_a_download_of_a_revision_that_is_not_public(
    api_client, data_fixture
):
    template = create_template(data_fixture, data_fixture.create_user())
    revision = data_fixture.set_user_template_revision_states(
        template, ["private", "public"]
    )
    _, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:jobs:list"),
        {
            "type": "download_user_template",
            "slug": template.slug,
            "revision_id": template.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TEMPLATE_UPDATED"
