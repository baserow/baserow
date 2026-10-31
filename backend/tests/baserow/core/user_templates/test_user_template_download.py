from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from baserow.api.jobs.serializers import JobSerializer
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Template
from baserow.core.user_templates.archive import (
    clear_template_archive_stamp,
    has_valid_archive,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import DownloadUserTemplateJob
from tests.baserow.core.user_templates.utils import (
    create_template,
    download,
    install_marks,
    request_download,
    run_job,
    store_template_archive,
    template_archive_names,
)

pytestmark = pytest.mark.usefixtures("use_tmp_media_root")

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_stamp():
    clear_template_archive_stamp()
    yield
    clear_template_archive_stamp()


def fake_build(side_effect=None):
    """
    Replaces the export of the archive by storing a file as the archive, like a
    build does, and counts the builds.
    """

    def build(handler, revision, **kwargs):
        if side_effect is not None:
            side_effect(revision)
        store_template_archive(revision)

    return patch.object(
        UserTemplateHandler, "build_template_archive", autospec=True, side_effect=build
    )


def create_public_template(data_fixture, owner):
    template = create_template(data_fixture, owner)
    return data_fixture.set_user_template_state(template, "public")


def add_revision(data_fixture, root):
    workspace = data_fixture.create_workspace(name="Revision")
    data_fixture.create_database_application(workspace=workspace)
    return data_fixture.create_user_template_revision(root, workspace=workspace)


def serialize(job):
    job = DownloadUserTemplateJob.objects.select_related("revision").get(id=job.id)
    return job_type_registry.get_serializer(job, JobSerializer).data


@pytest.mark.django_db
def test_download_reuses_a_valid_archive(data_fixture):
    owner = data_fixture.create_user()
    template = create_template(data_fixture, owner)

    with fake_build() as build:
        first = download(owner, template)
        second = download(owner, template)

    assert (first.state, second.state) == (JOB_FINISHED, JOB_FINISHED)
    assert first.id != second.id
    assert second.progress_percentage == 100
    assert build.call_count == 1
    assert len(template_archive_names(template)) == 1


@install_marks
@pytest.mark.parametrize("while_it_builds", [False, True])
def test_download_of_a_deleted_revision(data_fixture, while_it_builds):
    owner = data_fixture.create_user()
    template = create_template(data_fixture, owner)
    job = request_download(owner, template)

    def delete_the_revision(revision):
        Template.objects.filter(id=revision.id).delete()
        raise TemplateDoesNotExist()

    if not while_it_builds:
        Template.objects.filter(id=template.id).delete()
    # The deleted revision isn't saved back on the failed job, which the database
    # would refuse.
    with fake_build(side_effect=delete_the_revision):
        job = run_job(job)

    assert job.state == JOB_FAILED
    assert job.error_code == TemplateDoesNotExist.__name__
    assert job.revision_id is None
    # So the archive is not asked for anymore.
    assert serialize(job)["slug"] is None


def lose_access(data_fixture, change, template, user):
    if change == "private":
        Template.objects.filter(id=template.id).update(public_revision=None)
    elif change == "deactivated":
        # The template stays public, but the user can't sign in anymore.
        User.objects.filter(id=user.id).update(is_active=False)
    else:
        # Unlike install, which still finishes.
        Template.objects.filter(id=template.id).update(
            marked_for_deletion_at=timezone.now()
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,with_archive",
    [("private", False), ("deactivated", False), ("marked", True)],
)
def test_download_job_fails_when_access_is_lost_before_it_runs(
    data_fixture, change, with_archive
):
    user = data_fixture.create_user()
    template = create_public_template(data_fixture, data_fixture.create_user())
    if with_archive:
        # The reused archive isn't handed out either.
        store_template_archive(template)
    job = request_download(user, template)
    lose_access(data_fixture, change, template, user)

    with fake_build() as build:
        job = run_job(job)

    assert (job.state, job.error_code) == (JOB_FAILED, TemplateDoesNotExist.__name__)
    assert build.call_count == 0
    # Kept, so that the failed job still names the template.
    assert job.revision_id == template.id


@pytest.mark.django_db
def test_download_job_fails_when_access_is_lost_while_it_builds(data_fixture):
    user = data_fixture.create_user()
    template = create_public_template(data_fixture, data_fixture.create_user())
    # The access is read from the root, not from the downloaded revision.
    revision = add_revision(data_fixture, template)
    data_fixture.set_user_template_state(template, "public", revision=revision)
    job = request_download(user, template)
    assert job.revision_id == revision.id

    with fake_build(
        side_effect=lambda _: lose_access(data_fixture, "private", template, user)
    ) as build:
        job = run_job(job)

    assert (job.state, job.error_code) == (JOB_FAILED, TemplateDoesNotExist.__name__)
    assert build.call_count == 1
    assert job.revision_id == revision.id
    # The archive is kept, so that a later download with access reuses it.
    assert has_valid_archive(Template.objects.get(id=revision.id))
