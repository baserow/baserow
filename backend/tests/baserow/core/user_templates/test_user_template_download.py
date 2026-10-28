from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import pytest

from baserow.api.jobs.serializers import JobSerializer
from baserow.core.context import get_current_workspace_id
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED, JOB_PENDING
from baserow.core.jobs.handler import JobHandler
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

JOB_TYPES = "baserow.core.user_templates.job_types"


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


def visible_job_ids(user, jobs, base_model=None):
    return set(
        JobHandler.get_jobs_for_user(
            user, None, [job.id for job in jobs], base_model=base_model
        ).values_list("id", flat=True)
    )


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


@pytest.mark.django_db
def test_download_gets_the_running_job_of_the_revision(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    template = create_public_template(data_fixture, owner)

    job = request_download(owner, template)

    # Attaching doesn't count toward the maximum number of jobs of the user.
    assert request_download(viewer, template).id == job.id
    assert request_download(owner, template).id == job.id
    assert DownloadUserTemplateJob.objects.count() == 1

    with fake_build() as build:
        job = run_job(job)

    assert job.state == JOB_FINISHED
    assert build.call_count == 1


@pytest.mark.django_db
def test_download_doesnt_get_a_failed_or_stale_job(data_fixture):
    owner = data_fixture.create_user()
    template = create_public_template(data_fixture, owner)
    failed = request_download(owner, template)
    DownloadUserTemplateJob.objects.filter(id=failed.id).update(state=JOB_FAILED)

    stale = request_download(owner, template)
    assert stale.id != failed.id
    # A job older than a job can run can't end anymore.
    DownloadUserTemplateJob.objects.filter(id=stale.id).update(
        created_on=timezone.now()
        - timedelta(seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 1)
    )

    job = request_download(data_fixture.create_user(), template)
    assert job.id not in [failed.id, stale.id]
    assert job.state == JOB_PENDING


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
    assert serialize(job)["url"] is None


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
    assert serialize(job)["url"] is None
    # The archive is kept, so that a later download with access reuses it.
    assert has_valid_archive(Template.objects.get(id=revision.id))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"public_revision": None}, id="private"),
        pytest.param({"marked_for_deletion_at": timezone.now()}, id="marked"),
    ],
)
def test_download_job_of_another_user_is_hidden_without_access(data_fixture, changes):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    template = create_public_template(data_fixture, owner)
    job = request_download(owner, template)
    assert visible_job_ids(viewer, [job]) == {job.id}

    Template.objects.filter(id=template.id).update(**changes)

    assert visible_job_ids(viewer, [job]) == set()
    assert visible_job_ids(viewer, [job], DownloadUserTemplateJob) == set()
    assert visible_job_ids(owner, [job]) == {job.id}


@pytest.mark.django_db
def test_download_job_of_another_revision_is_hidden(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    template = create_public_template(data_fixture, owner)
    latest = add_revision(data_fixture, template)
    public_job = request_download(owner, template)
    DownloadUserTemplateJob.objects.update(state=JOB_FINISHED)
    latest_job = request_download(owner, template, latest=True)

    # The latest revision isn't public.
    assert visible_job_ids(viewer, [public_job, latest_job]) == {public_job.id}

    # Once the latest revision is public, the job of the former one is hidden.
    data_fixture.set_user_template_state(template, "public", revision=latest)

    assert visible_job_ids(viewer, [public_job, latest_job]) == {latest_job.id}
    assert visible_job_ids(owner, [public_job, latest_job]) == {
        public_job.id,
        latest_job.id,
    }


@pytest.mark.django_db
def test_download_jobs_of_other_users_beyond_the_limit_are_hidden(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    jobs = [
        DownloadUserTemplateJob.objects.create(
            user=owner, revision=create_public_template(data_fixture, owner)
        )
        for _ in range(2)
    ]
    own_job = request_download(viewer, create_template(data_fixture, viewer))

    with patch(f"{JOB_TYPES}.MAX_FOREIGN_DOWNLOAD_REVISIONS_TO_SCOPE", 2):
        assert visible_job_ids(viewer, [*jobs, own_job]) == {
            jobs[0].id,
            jobs[1].id,
            own_job.id,
        }
    with patch(f"{JOB_TYPES}.MAX_FOREIGN_DOWNLOAD_REVISIONS_TO_SCOPE", 1):
        assert visible_job_ids(viewer, [*jobs, own_job]) == {own_job.id}
        # The type filtered listing scopes every job of the type.
        assert visible_job_ids(viewer, [], DownloadUserTemplateJob) == {own_job.id}


@pytest.mark.django_db
def test_download_jobs_of_other_users_query_count(data_fixture):
    viewer = data_fixture.create_user()
    template = create_public_template(data_fixture, data_fixture.create_user())

    def count_queries(job_count):
        jobs = [
            DownloadUserTemplateJob.objects.create(
                user=data_fixture.create_user(), revision=template
            )
            for _ in range(job_count)
        ]
        with CaptureQueriesContext(connection) as queries:
            assert visible_job_ids(viewer, jobs) == {job.id for job in jobs}
        return len(queries)

    assert count_queries(1) == count_queries(5)


@pytest.mark.django_db
def test_download_job_serializer(data_fixture):
    owner = data_fixture.create_user()
    template = create_template(data_fixture, owner, name="Sales pipeline")
    job = request_download(owner, template)

    data = serialize(job)
    assert data["url"] is None
    assert data["file_name"] == "sales-pipeline.zip"

    store_template_archive(template)
    # Like a worker right before it saves the job: the state is cached first. The
    # toast stops polling once it's finished, so the URL is there too.
    job.set_state_finished()

    def url_with_the_workspace(name):
        return f"{get_current_workspace_id()}/{name}"

    with patch(f"{JOB_TYPES}.get_default_storage") as storage:
        storage.return_value.url.side_effect = url_with_the_workspace
        data = serialize(job)

    # Signed with the workspace of the revision, see secure file serve.
    assert data["url"] == f"{template.workspace_id}/{template.archive.name}"
    assert get_current_workspace_id() is None

    Template.objects.filter(id=template.id).update(name="!!!")
    assert serialize(job)["file_name"] == "template.zip"

    Template.objects.filter(id=template.id).delete()
    assert serialize(job)["url"] is None
    assert serialize(job)["file_name"] is None
