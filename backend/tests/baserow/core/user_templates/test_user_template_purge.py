import threading
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import (
    Application,
    InstallTemplateJob,
    Template,
    Workspace,
)
from baserow.core.storage import get_default_storage
from baserow.core.user_templates import tasks
from baserow.core.user_templates.archive import template_archive_dir
from baserow.core.user_templates.constants import USER_TEMPLATE_DELETION_GRACE_PERIOD
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import (
    CreateUserTemplateJob,
    DownloadUserTemplateJob,
    UserTemplateContentToDelete,
)
from baserow.core.user_templates.tasks import delete_orphaned_user_template_workspaces
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_content,
    long_ago,
    purge,
    store_template_archive,
    template_archive_names,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def create_family(data_fixture, *, marked_for_deletion_at=None, revisions=2):
    """
    A user template whose root is public and whose revision 2 is shared. Revision 3
    only changed the details, so it shares the content of revision 2. It was
    created, updated and installed by jobs that ended.
    """

    if marked_for_deletion_at is None:
        marked_for_deletion_at = long_ago()
    owner = data_fixture.create_user()
    source_workspace = data_fixture.create_workspace(user=owner, name="Source")
    data_fixture.create_database_application(workspace=source_workspace)

    workspace, archive = create_content(data_fixture)
    root = data_fixture.create_user_template(
        user=owner, workspace=workspace, archive=archive, icon=ICON
    )
    family = [root]
    contents = [(workspace, archive)]
    if revisions >= 1:
        workspace_2, archive_2 = create_content(data_fixture)
        family.append(
            data_fixture.create_user_template_revision(
                root, workspace=workspace_2, archive=archive_2, icon=ICON
            )
        )
        contents.append((workspace_2, archive_2))
    for _ in range(revisions - 1):
        family.append(
            data_fixture.create_user_template_revision(
                root, workspace=workspace_2, archive=archive_2, icon=ICON
            )
        )
    Template.objects.filter(id=root.id).update(
        public_revision=root,
        shared_revision=family[1] if len(family) > 1 else root,
        marked_for_deletion_at=marked_for_deletion_at,
    )

    jobs = [
        CreateUserTemplateJob.objects.create(
            user=owner,
            state=JOB_FINISHED,
            source_workspace=source_workspace,
            name=root.name,
            icon=ICON,
            template=root,
            revision=root,
            # A finished job keeps pointing at the content of its revision.
            template_workspace=root.workspace,
            archive_name=root.archive.name,
        )
    ]
    for base_revision, revision in zip(family, family[1:]):
        jobs.append(
            CreateUserTemplateJob.objects.create(
                user=owner,
                state=JOB_FINISHED,
                source_workspace=source_workspace,
                name=root.name,
                icon=ICON,
                template=root,
                base_revision=base_revision,
                revision=revision,
                template_workspace=revision.workspace,
                archive_name=revision.archive.name,
            )
        )
    install_workspace = data_fixture.create_workspace(user=owner, name="Installed")
    jobs.append(
        InstallTemplateJob.objects.create(
            user=owner,
            state=JOB_FINISHED,
            workspace=install_workspace,
            template=root,
        )
    )
    installed = data_fixture.create_database_application(
        workspace=install_workspace, installed_from_template=root
    )
    for job in jobs:
        job.set_cached_state()

    return {
        "owner": owner,
        "root": root,
        "family": family,
        "contents": contents,
        "jobs": jobs,
        "source_workspace": source_workspace,
        "install_workspace": install_workspace,
        "installed": installed,
    }


def assert_family_kept(family):
    assert Template.objects.filter(id__in=[t.id for t in family["family"]]).count() == (
        len(family["family"])
    )
    for workspace, archive in family["contents"]:
        assert Workspace.objects.filter(id=workspace.id).exists()
        assert get_default_storage().exists(archive)


def assert_family_removed(family):
    family_ids = [template.id for template in family["family"]]
    assert not Template.objects.filter(id__in=family_ids).exists()
    job_ids = [job.id for job in family["jobs"]]
    assert not CreateUserTemplateJob.objects.filter(id__in=job_ids).exists()
    assert not InstallTemplateJob.objects.filter(id__in=job_ids).exists()
    for workspace, archive in family["contents"]:
        assert not Workspace.objects_and_trash.filter(id=workspace.id).exists()
        assert not get_default_storage().exists(archive)
    for job_id in job_ids:
        assert cache.get(job_progress_key(job_id)) is None


def test_purge_removes_a_deleted_template_after_the_grace_period(data_fixture):
    family = create_family(data_fixture)
    other = create_family(data_fixture, marked_for_deletion_at=timezone.now())

    purge()

    assert_family_removed(family)
    assert not UserTemplateContentToDelete.objects.exists()
    # The workspace the content was copied from, and the installed copy, are kept.
    assert Workspace.objects.filter(id=family["source_workspace"].id).exists()
    installed = Application.objects.get(id=family["installed"].id)
    assert installed.installed_from_template_id is None
    assert installed.workspace_id == family["install_workspace"].id
    # Another template is untouched.
    assert_family_kept(other)
    assert Workspace.objects.filter(id=other["source_workspace"].id).exists()
    assert Application.objects.get(
        id=other["installed"].id
    ).installed_from_template_id == (other["root"].id)
    for job in other["jobs"]:
        assert cache.get(job_progress_key(job.id)) is not None

    with CaptureQueriesContext(connection) as queries:
        purge()

    assert_family_removed(family)
    assert_family_kept(other)
    # Only the lookup of the templates to remove.
    assert len(queries) == 1


def test_purge_keeps_templates_that_arent_due(data_fixture):
    recent = create_family(
        data_fixture,
        marked_for_deletion_at=timezone.now()
        - USER_TEMPLATE_DELETION_GRACE_PERIOD
        + timedelta(minutes=1),
    )
    unmarked = data_fixture.create_user_template()
    official = data_fixture.create_template(marked_for_deletion_at=long_ago())

    purge()

    assert_family_kept(recent)
    assert Template.objects.filter(id__in=[unmarked.id, official.id]).count() == 2


def test_purge_keeps_content_used_outside_the_template(data_fixture):
    family = create_family(data_fixture)
    shared_workspace, shared_archive = family["contents"][1]
    data_fixture.create_user_template(
        workspace=shared_workspace, archive=shared_archive
    )

    purge()

    assert not Template.objects.filter(id=family["root"].id).exists()
    assert Workspace.objects.filter(id=shared_workspace.id).exists()
    assert get_default_storage().exists(shared_archive)
    workspace, archive = family["contents"][0]
    assert not Workspace.objects_and_trash.filter(id=workspace.id).exists()
    assert not get_default_storage().exists(archive)
    assert not UserTemplateContentToDelete.objects.exists()


def create_pending_update_job(family):
    return CreateUserTemplateJob.objects.create(
        user=family["owner"],
        state=JOB_PENDING,
        name="Update",
        icon=ICON,
        template=family["root"],
        base_revision=family["family"][-1],
    )


def create_running_create_job(family):
    # It committed the template, but didn't save that it finished yet.
    return CreateUserTemplateJob.objects.create(
        user=family["owner"],
        state=JOB_STARTED,
        source_workspace=family["source_workspace"],
        name="Create",
        icon=ICON,
        template=family["root"],
        revision=family["root"],
    )


def create_install_job(state):
    def create(family):
        return InstallTemplateJob.objects.create(
            user=family["owner"],
            state=state,
            workspace=family["install_workspace"],
            template=family["family"][-1],
        )

    return create


BUSY_JOBS = [
    pytest.param(create_pending_update_job, id="pending_update"),
    pytest.param(create_running_create_job, id="running_create"),
    pytest.param(create_install_job(JOB_PENDING), id="pending_install"),
    pytest.param(create_install_job(JOB_STARTED), id="running_install"),
]


@patch("baserow.core.user_templates.handler.USER_TEMPLATE_PURGE_BATCH_SIZE", 1)
@pytest.mark.parametrize("create_job", BUSY_JOBS)
def test_purge_waits_for_the_jobs_of_the_template(data_fixture, create_job):
    # The template deleted first has a job, on a revision for the installs, so it
    # would take the only slot of the batch if it wasn't left out.
    family = create_family(data_fixture, revisions=1)
    job = create_job(family)
    other = create_family(data_fixture, revisions=1)

    purge()

    assert_family_kept(family)
    assert type(job).objects.filter(id=job.id).exists()
    assert_family_removed(other)

    type(job).objects.filter(id=job.id).update(state=JOB_FINISHED)
    purge()

    assert_family_removed(family)
    assert not type(job).objects.filter(id=job.id).exists()


@patch("baserow.core.user_templates.handler.USER_TEMPLATE_PURGE_BATCH_SIZE", 1)
def test_purge_waits_for_the_downloads_of_the_template(data_fixture):
    family = create_family(data_fixture)
    add_template_archives(family)
    job = DownloadUserTemplateJob.objects.create(
        user=data_fixture.create_user(),
        state=JOB_STARTED,
        revision=family["family"][-1],
    )
    other = create_family(data_fixture, revisions=1)

    purge()

    assert_family_kept(family)
    assert_family_removed(other)

    DownloadUserTemplateJob.objects.filter(id=job.id).update(state=JOB_FINISHED)
    purge()

    assert_family_removed(family)
    assert_template_archives_removed(family)
    # The job is kept, like any job of the user, without the deleted revision.
    job.refresh_from_db()
    assert job.state == JOB_FINISHED
    assert job.revision_id is None


def test_purge_of_a_template_sees_a_download_started_after_it_was_picked(
    data_fixture,
):
    family = create_family(data_fixture)
    DownloadUserTemplateJob.objects.create(
        user=data_fixture.create_user(), state=JOB_PENDING, revision=family["root"]
    )

    # The jobs are read again once they're locked.
    assert not UserTemplateHandler()._delete_marked_template(family["root"].id)

    assert_family_kept(family)


def test_purge_sees_a_failed_job_started_before_it_locks_the_jobs(data_fixture):
    family = create_family(data_fixture)
    job = create_pending_update_job(family)
    CreateUserTemplateJob.objects.filter(id=job.id).update(state=JOB_FAILED)
    locked = threading.Event()
    errors = []

    # The late task of a failed job locks it and starts it, see `run_async_job`.
    def start_the_failed_job():
        try:
            with transaction.atomic():
                started = JobHandler.lock_job(job)
                started.set_state_started()
                started.save(update_fields=["state", "updated_on"])
                locked.set()
                # The purge reads the jobs meanwhile, and waits for the lock.
                threading.Event().wait(0.5)
        except Exception as error:
            errors.append(error)
        finally:
            connection.close()

    thread = threading.Thread(target=start_the_failed_job)
    thread.start()
    assert locked.wait(timeout=10)
    purge()
    thread.join(timeout=10)

    assert errors == []
    assert_family_kept(family)
    assert CreateUserTemplateJob.objects.get(id=job.id).state == JOB_STARTED


def test_purge_skips_a_template_locked_by_another_transaction(data_fixture):
    family = create_family(data_fixture)
    locked = threading.Event()
    release = threading.Event()
    errors = []

    def lock_the_root():
        try:
            with transaction.atomic():
                Template.objects.select_for_update().get(id=family["root"].id)
                locked.set()
                release.wait(timeout=5)
        except Exception as error:
            errors.append(error)
        finally:
            connection.close()

    thread = threading.Thread(target=lock_the_root)
    thread.start()
    assert locked.wait(timeout=10)
    try:
        purge()
        assert not release.is_set()
        assert_family_kept(family)
    finally:
        release.set()
        thread.join(timeout=10)

    assert errors == []
    purge()

    assert_family_removed(family)


def test_purge_removes_what_an_unfinished_job_left(data_fixture):
    family = create_family(data_fixture)
    job_workspace, job_archive = create_content(data_fixture, name="Copy")
    job = CreateUserTemplateJob.objects.create(
        user=family["owner"],
        state=JOB_FAILED,
        name="Update",
        icon=ICON,
        template=family["root"],
        base_revision=family["family"][-1],
        template_workspace=job_workspace,
        archive_name=job_archive,
    )

    purge()

    assert_family_removed(family)
    assert not CreateUserTemplateJob.objects.filter(id=job.id).exists()
    assert not Workspace.objects_and_trash.filter(id=job_workspace.id).exists()
    assert not get_default_storage().exists(job_archive)
    assert not UserTemplateContentToDelete.objects.exists()


def test_purge_retries_content_whose_deletion_failed(data_fixture):
    family = create_family(data_fixture)
    archives = [archive for _, archive in family["contents"]]

    with patch.object(
        get_default_storage().__class__,
        "delete",
        side_effect=OSError("Storage unavailable."),
    ):
        purge()

    assert not Template.objects.filter(id=family["root"].id).exists()
    assert all(get_default_storage().exists(archive) for archive in archives)
    assert sorted(
        UserTemplateContentToDelete.objects.values_list("archive_name", flat=True)
    ) == sorted(archives)

    delete_orphaned_user_template_workspaces()

    assert_family_removed(family)
    assert not UserTemplateContentToDelete.objects.exists()


def add_template_archives(family):
    """
    Gives the revisions of the family the archives their downloads built: the
    last one refers to its archive, the others have a file a build left behind.
    """

    names = []
    for revision in family["family"][:-1]:
        names.append(
            get_default_storage().save(
                f"{template_archive_dir(revision.id)}left.zip", ContentFile(b"left")
            )
        )
    # It shares the content of the revision before, which keeps its archive.
    names.append(store_template_archive(family["family"][-1]))
    return names


def assert_template_archives_removed(family):
    for revision in family["family"]:
        assert not get_default_storage().exists(template_archive_dir(revision.id))


def test_purge_removes_the_archives_of_every_revision(data_fixture):
    family = create_family(data_fixture)
    other = create_family(data_fixture, marked_for_deletion_at=timezone.now())
    add_template_archives(family)
    other_names = add_template_archives(other)

    purge()

    assert_family_removed(family)
    assert_template_archives_removed(family)
    assert not UserTemplateContentToDelete.objects.exists()
    assert sum(
        (template_archive_names(revision) for revision in other["family"]), []
    ) == sorted(other_names)


def test_purge_continues_after_a_template_fails(data_fixture):
    broken = create_family(data_fixture)
    other = create_family(data_fixture)
    delete_marked_template = UserTemplateHandler._delete_marked_template

    def fail_for_broken(handler, root_id):
        if root_id == broken["root"].id:
            raise ValueError("Something is wrong.")
        return delete_marked_template(handler, root_id)

    with (
        patch.object(
            UserTemplateHandler,
            "_delete_marked_template",
            autospec=True,
            side_effect=fail_for_broken,
        ),
        patch("baserow.core.user_templates.handler.logger") as logger,
    ):
        purge()

    logger.exception.assert_called_once()
    assert_family_kept(broken)
    assert_family_removed(other)


@patch("baserow.core.user_templates.handler.USER_TEMPLATE_PURGE_BATCH_SIZE", 1)
def test_purge_retries_a_failing_template_after_the_others(data_fixture):
    broken = create_family(data_fixture, revisions=0)
    other = create_family(data_fixture, revisions=0)
    delete_marked_template = UserTemplateHandler._delete_marked_template

    def fail_for_broken(handler, root_id):
        if root_id == broken["root"].id:
            raise ValueError("Something is wrong.")
        return delete_marked_template(handler, root_id)

    with patch.object(
        UserTemplateHandler,
        "_delete_marked_template",
        autospec=True,
        side_effect=fail_for_broken,
    ):
        before = timezone.now()
        purge()

        assert_family_kept(broken)
        assert_family_kept(other)
        # It goes to the back of the queue, and is tried again after another grace
        # period.
        assert Template.objects.get(id=broken["root"].id).marked_for_deletion_at > (
            before
        )

        purge()

    assert_family_kept(broken)
    assert_family_removed(other)


@patch("baserow.core.user_templates.handler.USER_TEMPLATE_PURGE_BATCH_SIZE", 1)
def test_purge_removes_the_template_deleted_first_first(data_fixture):
    deleted_last = create_family(data_fixture, revisions=0)
    deleted_first = create_family(
        data_fixture, revisions=0, marked_for_deletion_at=long_ago() - timedelta(1)
    )

    purge()

    assert_family_kept(deleted_last)
    assert_family_removed(deleted_first)


def test_purge_removes_the_template_when_clearing_the_job_cache_fails(data_fixture):
    family = create_family(data_fixture)

    with (
        patch(
            "baserow.core.user_templates.handler.cache.delete_many",
            side_effect=ConnectionError("Cache unavailable."),
        ),
        patch("baserow.core.user_templates.handler.logger") as logger,
    ):
        purge()

    assert not Template.objects.filter(id=family["root"].id).exists()
    for workspace, archive in family["contents"]:
        assert not Workspace.objects_and_trash.filter(id=workspace.id).exists()
        assert not get_default_storage().exists(archive)
    assert not UserTemplateContentToDelete.objects.exists()
    # The template was removed, only the cache wasn't cleared.
    logger.exception.assert_called_once()
    assert "cache" in logger.exception.call_args.args[0]


def test_purge_stops_when_it_runs_out_of_time(data_fixture):
    # The removal is mocked, so the templates need no content.
    roots = [
        data_fixture.create_user_template(marked_for_deletion_at=long_ago())
        for _ in range(2)
    ]

    with patch.object(
        UserTemplateHandler,
        "_delete_marked_template",
        autospec=True,
        side_effect=SoftTimeLimitExceeded(),
    ) as delete_marked_template:
        with pytest.raises(SoftTimeLimitExceeded):
            purge()

    delete_marked_template.assert_called_once()
    assert Template.objects.filter(id__in=[root.id for root in roots]).count() == 2


def test_deleting_tracked_content_stops_when_it_runs_out_of_time(data_fixture):
    UserTemplateContentToDelete.objects.create(workspace_id=None, archive_name="a.zip")

    with patch.object(
        UserTemplateHandler,
        "delete_content_without_template",
        side_effect=SoftTimeLimitExceeded(),
    ):
        with pytest.raises(SoftTimeLimitExceeded):
            UserTemplateHandler().delete_content_of_unfinished_jobs()

    assert UserTemplateContentToDelete.objects.exists()


def count_purge_queries(root_id):
    # Without the deletion of the content after the commit, which depends on what
    # the workspaces hold.
    with (
        patch.object(UserTemplateHandler, "_delete_tracked_content"),
        CaptureQueriesContext(connection) as queries,
    ):
        assert UserTemplateHandler()._delete_marked_template(root_id)
    return len(queries)


def test_purge_queries_dont_depend_on_the_size_of_the_template(data_fixture):
    # Both have revisions, Django looks up the related rows of each model once.
    small = create_family(data_fixture, revisions=1)
    large = create_family(data_fixture, revisions=4)

    assert count_purge_queries(small["root"].id) == count_purge_queries(
        large["root"].id
    )


def test_cleanup_task_removes_a_batch_of_templates_per_run(data_fixture):
    families = [create_family(data_fixture, revisions=0) for _ in range(3)]
    job_workspace, job_archive = create_content(data_fixture, name="Copy")
    CreateUserTemplateJob.objects.create(
        user=data_fixture.create_user(),
        state=JOB_FAILED,
        name="Copy",
        icon=ICON,
        template_workspace=job_workspace,
        archive_name=job_archive,
    )

    with patch("baserow.core.user_templates.handler.USER_TEMPLATE_PURGE_BATCH_SIZE", 2):
        tasks.delete_orphaned_user_template_workspaces()

        assert_family_removed(families[0])
        assert_family_removed(families[1])
        assert_family_kept(families[2])
        # The sweep ran too.
        assert not Workspace.objects_and_trash.filter(id=job_workspace.id).exists()
        assert not get_default_storage().exists(job_archive)

        tasks.delete_orphaned_user_template_workspaces()

    assert_family_removed(families[2])
