import os
import threading
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.db import OperationalError, connection
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.action.models import Action
from baserow.core.cache import local_cache
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import (
    Application,
    ImportExportResource,
    InstallTemplateJob,
    Template,
    TrashEntry,
    UserFile,
    WorkspaceUser,
)
from baserow.core.user_templates.actions import DeleteUserTemplateActionType
from baserow.core.user_templates.constants import USER_TEMPLATE_DELETION_GRACE_PERIOD
from baserow.core.user_templates.exceptions import (
    TemplateBlocked,
    TemplateHasNoContent,
)
from baserow.core.user_templates.handler import UserTemplateHandler

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")
# The install exports and imports, so it runs outside a test transaction.
install_test = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def install_marks(test):
    for mark in reversed(install_test):
        test = mark(test)
    return test


def _create_revisions(data_fixture, owner):
    """
    A user template of the owner with three revisions, each with a database in its
    workspace. The second revision is approved and public.
    """

    root = data_fixture.create_user_template(user=owner)
    data_fixture.create_database_application(workspace=root.workspace)
    revisions = [root]
    for _ in range(2):
        revision = data_fixture.create_user_template_revision(
            root, review_state=Template.ReviewState.APPROVED
        )
        data_fixture.create_database_application(workspace=revision.workspace)
        revisions.append(revision)
    Template.objects.filter(id=root.id).update(public_revision=revisions[1])
    root.refresh_from_db()
    return revisions


def _start_install(user, root, latest=False):
    # Only one install job of a user can run at a time.
    InstallTemplateJob.objects.filter(user=user).delete()
    return JobHandler().create_and_start_job(
        user,
        InstallTemplateJobType.type,
        workspace_id=user.workspaceuser_set.first().workspace_id,
        template_id=root.id,
        latest=latest,
    )


@pytest.mark.django_db
def test_install_user_template_pins_revision(data_fixture):
    owner = data_fixture.create_user()
    staff = data_fixture.create_user(is_staff=True)
    viewer = data_fixture.create_user()
    for user in [owner, staff, viewer]:
        data_fixture.create_workspace(user=user)
    root, revision_2, revision_3 = _create_revisions(data_fixture, owner)

    # Everyone installs the public revision, the owner too, while a newer revision
    # exists. Only the owner can ask for the latest one, as from "Your templates".
    for user in [owner, staff, viewer]:
        assert _start_install(user, root).template_id == revision_2.id
    assert _start_install(owner, root, latest=True).template_id == revision_3.id
    for user in [staff, viewer]:
        with pytest.raises(TemplateDoesNotExist):
            _start_install(user, root, latest=True)

    # The owner installs the latest revision while the template isn't public.
    Template.objects.filter(id=root.id).update(public_revision=None)
    assert _start_install(owner, root).template_id == revision_3.id


@pytest.mark.django_db
def test_install_user_template_pins_details_only_revision(data_fixture):
    owner = data_fixture.create_user()
    data_fixture.create_workspace(user=owner)
    root = data_fixture.create_user_template(user=owner)
    data_fixture.create_database_application(workspace=root.workspace)
    # An update of the details only shares the workspace of the first revision.
    revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace
    )

    job = _start_install(owner, root)

    assert job.template_id == revision.id
    assert job.template.workspace_id == root.workspace_id


@pytest.mark.django_db
def test_check_install_access(data_fixture):
    owner = data_fixture.create_user()
    staff = data_fixture.create_user(is_staff=True)
    viewer = data_fixture.create_user()
    inactive = data_fixture.create_user(is_active=False)
    root, revision_2, revision_3 = _create_revisions(data_fixture, owner)
    handler = UserTemplateHandler()

    for user in [owner, staff, viewer]:
        handler.check_install_access(user, revision_2)
    with pytest.raises(TemplateDoesNotExist):
        handler.check_install_access(inactive, revision_2)

    # The pinned revision is still installed after the public revision moved, and
    # after the template was marked for deletion.
    Template.objects.filter(id=root.id).update(
        public_revision=revision_3, marked_for_deletion_at=timezone.now()
    )
    revision_2 = Template.objects.get(id=revision_2.id)
    handler.check_install_access(viewer, revision_2)

    Template.objects.filter(id=root.id).update(public_revision=None)
    revision_2 = Template.objects.get(id=revision_2.id)
    with pytest.raises(TemplateDoesNotExist):
        handler.check_install_access(viewer, revision_2)

    Template.objects.filter(id=root.id).update(
        public_revision=revision_2, blocked_at=timezone.now()
    )
    revision_2 = Template.objects.get(id=revision_2.id)
    with pytest.raises(TemplateBlocked):
        handler.check_install_access(owner, revision_2)
    # An instance admin has no access of its own.
    for user in [staff, viewer]:
        with pytest.raises(TemplateDoesNotExist):
            handler.check_install_access(user, revision_2)


def _add_database(data_fixture, workspace, name):
    database = data_fixture.create_database_application(workspace=workspace, name=name)
    table = data_fixture.create_database_table(database=database, name=f"{name} table")
    field = data_fixture.create_text_field(table=table, primary=True, name="Name")
    table.get_model().objects.create(**{field.db_column: f"{name} row"})
    return database


def _create_template(data_fixture, owner, names=("First", "Second")):
    """
    A user template of the owner, public, with a database per name in its
    workspace, each with a table and a row.
    """

    root = data_fixture.create_user_template(user=owner, name="Mine")
    for name in names:
        _add_database(data_fixture, root.workspace, name)
    Template.objects.filter(id=root.id).update(public_revision=root)
    root.refresh_from_db()
    return root


def _request_install(user, workspace, root, latest=False):
    """Requests an install without running it, like a job waiting in the queue."""

    with patch("baserow.core.jobs.handler.run_async_job"):
        return JobHandler().create_and_start_job(
            user,
            InstallTemplateJobType.type,
            workspace_id=workspace.id,
            template_id=root.id,
            latest=latest,
        )


def _run(job):
    # A worker clears the local cache before each task, see `config/celery.py`.
    local_cache.clear()
    run_async_job(job.id)
    return InstallTemplateJob.objects.get(id=job.id)


def _install(user, workspace, root, latest=False):
    return _run(_request_install(user, workspace, root, latest))


def _installed_names(workspace):
    return sorted(
        Application.objects_and_trash.filter(workspace=workspace).values_list(
            "name", flat=True
        )
    )


def _counts():
    return {"actions": Action.objects.count(), "files": UserFile.objects.count()}


def _assert_nothing_installed(workspace, root, counts):
    assert not Application.objects_and_trash.filter(workspace=workspace).exists()
    assert not TrashEntry.objects.filter(workspace=workspace).exists()
    assert _counts() == counts
    assert Template.objects.get(id=root.id).install_count == 0


def _import_application_raising(exception, on_call=2, before=None):
    """
    Patches the import of an application so that the import of the `on_call`-th
    application raises, or first calls `before`.
    """

    import_application = ImportExportHandler.import_application
    calls = []

    def import_application_raising(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == on_call:
            if before is not None:
                before()
            if exception is not None:
                raise exception
        return import_application(self, *args, **kwargs)

    return patch.object(
        ImportExportHandler, "import_application", import_application_raising
    )


@install_marks
def test_install_user_template_job(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    updated_on = root.updated_on

    job = _install(owner, target, root)

    assert job.state == JOB_FINISHED
    applications = list(
        Application.objects.filter(workspace=target).order_by("order", "id")
    )
    assert [app.name for app in applications] == ["First", "Second"]
    assert job.installed_applications == [app.id for app in applications]
    assert {app.installed_from_template_id for app in applications} == {root.id}
    for application in applications:
        table = application.specific.table_set.get()
        primary = table.field_set.get(primary=True)
        assert list(
            table.get_model().objects.values_list(primary.db_column, flat=True)
        ) == [f"{application.name} row"]
    root.refresh_from_db()
    assert root.install_count == 1
    # The count is bumped without saving the root, which orders the lists.
    assert root.updated_on == updated_on
    assert not ImportExportResource.objects.filter(marked_for_deletion=False).exists()


@install_marks
def test_install_user_template_job_counts_each_install_on_the_root(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    owner_target = data_fixture.create_workspace(user=owner)
    viewer_target = data_fixture.create_workspace(user=viewer)
    root = _create_template(data_fixture, owner)
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    _add_database(data_fixture, revision.workspace, "Latest")

    assert _install(owner, owner_target, root, latest=True).template_id == revision.id
    assert _install(viewer, viewer_target, root).template_id == root.id

    assert _installed_names(owner_target) == ["Latest"]
    assert _installed_names(viewer_target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 2
    assert Template.objects.get(id=revision.id).install_count == 0


@install_marks
def test_concurrent_installs_both_count(data_fixture, test_thread):
    owner = data_fixture.create_user()
    # One install job runs at a time per user.
    viewer = data_fixture.create_user()
    first_target = data_fixture.create_workspace(user=owner)
    second_target = data_fixture.create_workspace(user=viewer)
    root = _create_template(data_fixture, owner)
    first_job = _request_install(owner, first_target, root)
    second_job = _request_install(viewer, second_target, root)
    check_install_access = UserTemplateHandler.check_install_access
    second_has_read = threading.Event()
    first_is_done = threading.Event()

    def check_then_wait_for_the_first_install(self, user, revision):
        check_install_access(self, user, revision)
        if user.id == viewer.id:
            # The second install has read the template, with its count, before
            # the first one commits its own.
            second_has_read.set()
            assert first_is_done.wait(30)

    def run_second_job():
        try:
            run_async_job(second_job.id)
        finally:
            connection.close()

    with (
        patch.object(
            UserTemplateHandler,
            "check_install_access",
            check_then_wait_for_the_first_install,
        ),
        test_thread(run_second_job) as thread,
    ):
        thread.start()
        assert second_has_read.wait(30)
        assert _run(first_job).state == JOB_FINISHED
        first_is_done.set()
        assert thread.thread_stopped.wait(30)

    assert InstallTemplateJob.objects.get(id=second_job.id).state == JOB_FINISHED
    assert _installed_names(second_target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 2


@install_marks
def test_install_user_template_job_redelivered_after_it_finished(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _install(owner, target, root)

    with patch.object(
        UserTemplateHandler,
        "export_template_content",
        side_effect=AssertionError("The template was exported again."),
    ) as export:
        redelivered = _run(job)

    assert redelivered.state == JOB_FINISHED
    assert redelivered.installed_applications == job.installed_applications
    assert _installed_names(target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 1
    export.assert_not_called()


@install_marks
def test_install_second_commit_of_same_job_keeps_first(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    check_install_access = UserTemplateHandler.check_install_access
    first_run = {}

    def commit_another_run_first(self, *args):
        # A second delivery of the job loaded it before the first one committed.
        if not first_run:
            first_run["job"] = None
            first_run["job"] = _run(job)
        check_install_access(self, *args)

    with patch.object(
        UserTemplateHandler, "check_install_access", commit_another_run_first
    ):
        second_run = _run(job)

    first_ids = first_run["job"].installed_applications
    assert first_run["job"].state == JOB_FINISHED
    assert second_run.state == JOB_FINISHED
    assert second_run.installed_applications == first_ids
    assert sorted(
        Application.objects_and_trash.filter(workspace=target).values_list(
            "id", flat=True
        )
    ) == sorted(first_ids)
    assert not TrashEntry.objects.filter(workspace=target).exists()
    assert Template.objects.get(id=root.id).install_count == 1


@install_marks
def test_install_failed_run_keeps_the_commit_of_another_run(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    export_template_content = UserTemplateHandler.export_template_content
    first_run = {}

    def export_failing_after_another_run(self, *args, **kwargs):
        # A second delivery of the job fails before its commit, after the first
        # one committed.
        if not first_run:
            first_run["job"] = None
            first_run["job"] = _run(job)
            raise RuntimeError("Export failed")
        return export_template_content(self, *args, **kwargs)

    with patch.object(
        UserTemplateHandler,
        "export_template_content",
        export_failing_after_another_run,
    ):
        second_run = _run(job)

    first_ids = first_run["job"].installed_applications
    assert first_ids
    assert second_run.state == JOB_FINISHED
    assert second_run.installed_applications == first_ids
    assert _installed_names(target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 1


@install_marks
def test_install_pinned_revision_survives_content_update(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)

    # A content update commits while the install waits in the queue.
    revision = data_fixture.create_user_template_revision(root)
    _add_database(data_fixture, revision.workspace, "Updated")

    job = _run(job)

    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]
    assert set(
        Application.objects.filter(workspace=target).values_list(
            "installed_from_template_id", flat=True
        )
    ) == {root.id}


@install_marks
def test_install_pinned_revision_with_details_only_update(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace
    )
    job = _request_install(owner, target, root, latest=True)
    # Another update of the details only, after the request.
    data_fixture.create_user_template_revision(root, workspace=root.workspace)

    job = _run(job)

    assert job.state == JOB_FINISHED
    assert job.template_id == revision.id
    assert _installed_names(target) == ["First", "Second"]
    assert set(
        Application.objects.filter(workspace=target).values_list(
            "installed_from_template_id", flat=True
        )
    ) == {revision.id}


@install_marks
def test_public_viewer_installs_pinned_public_revision_after_it_moved(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    target = data_fixture.create_workspace(user=viewer)
    root = _create_template(data_fixture, owner)
    job = _request_install(viewer, target, root)
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    _add_database(data_fixture, revision.workspace, "Latest")
    Template.objects.filter(id=root.id).update(public_revision=revision)

    job = _run(job)

    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]


def _refused_after_request(data_fixture, flip, installer="owner"):
    """
    Requests an install, flips something with `flip(context)` before the job
    runs, then runs it.
    """

    owner = data_fixture.create_user()
    users = {
        "owner": owner,
        "staff": data_fixture.create_user(is_staff=True),
        "viewer": data_fixture.create_user(),
    }
    user = users[installer]
    target = data_fixture.create_workspace(user=user)
    root = _create_template(data_fixture, owner)
    job = _request_install(user, target, root)
    counts = _counts()

    flip({"root": root, "user": user, "owner": owner, "target": target, "job": job})

    return _run(job), target, root, counts


def _block(context):
    Template.objects.filter(id=context["root"].id).update(blocked_at=timezone.now())


def _make_private(context):
    Template.objects.filter(id=context["root"].id).update(public_revision=None)


def _mark_for_deletion(context):
    Template.objects.filter(id=context["root"].id).update(
        marked_for_deletion_at=timezone.now()
    )


def _remove_from_target(context):
    WorkspaceUser.objects.filter(
        user=context["user"], workspace=context["target"]
    ).delete()


def _deactivate(context):
    type(context["user"]).objects.filter(id=context["user"].id).update(is_active=False)


def _detach_workspace(context):
    Template.objects.filter(id=context["root"].id).update(workspace=None)


def _trash_content(context):
    Application.objects.filter(workspace=context["root"].workspace).update(trashed=True)


@pytest.mark.parametrize(
    "installer,flip,error_code",
    [
        ("owner", _block, "TemplateBlocked"),
        ("viewer", _make_private, "TemplateDoesNotExist"),
        ("viewer", _block, "TemplateDoesNotExist"),
        ("staff", _block, "TemplateDoesNotExist"),
        ("owner", _remove_from_target, "UserNotInWorkspace"),
        ("viewer", _remove_from_target, "UserNotInWorkspace"),
        # An inactive user doesn't count as a member, which is checked first.
        ("owner", _deactivate, "UserNotInWorkspace"),
        ("owner", _detach_workspace, "TemplateHasNoContent"),
        ("owner", _trash_content, "TemplateHasNoContent"),
    ],
)
@install_marks
def test_install_user_template_job_access_checked_again_when_it_runs(
    data_fixture, installer, flip, error_code
):
    job, target, root, counts = _refused_after_request(data_fixture, flip, installer)

    assert job.state == JOB_FAILED
    assert job.error_code == error_code
    assert job.human_readable_error
    assert job.installed_applications == []
    _assert_nothing_installed(target, root, counts)


@pytest.mark.parametrize(
    "installer,flip",
    [
        ("viewer", _mark_for_deletion),
        ("owner", _mark_for_deletion),
    ],
)
@install_marks
def test_install_user_template_job_still_runs_after(data_fixture, installer, flip):
    # The installs already running when a template is deleted finish.
    job, target, root, _ = _refused_after_request(data_fixture, flip, installer)

    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 1


@install_marks
def test_install_user_template_empty_revision_workspace(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner, names=())

    with pytest.raises(TemplateHasNoContent):
        _request_install(owner, target, root)

    assert not InstallTemplateJob.objects.exists()


@install_marks
def test_install_user_template_job_fails_on_import_of_second_application(
    data_fixture,
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    with (
        _import_application_raising(RuntimeError("Import failed")),
        pytest.raises(RuntimeError),
    ):
        _run(job)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.installed_applications == []
    _assert_nothing_installed(target, root, counts)
    assert not ImportExportResource.objects.filter(marked_for_deletion=False).exists()


@install_marks
def test_install_user_template_job_fails_at_the_commit_point(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()
    lock_job = JobHandler.lock_job
    calls = []

    def lock_job_raising(job):
        calls.append(job)
        # The first lock is taken when the job starts, the second one at the
        # commit point, after the import.
        if len(calls) == 2:
            assert Application.objects.filter(workspace=target).count() == 2
            raise RuntimeError("Lock failed")
        return lock_job(job)

    with (
        patch.object(JobHandler, "lock_job", lock_job_raising),
        pytest.raises(RuntimeError),
    ):
        _run(job)

    # The third lock looks for the commit of another run of the job.
    assert len(calls) == 3
    job.refresh_from_db()
    assert job.state == JOB_FAILED
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_fails_after_the_ids_are_set(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()
    commit_install = InstallTemplateJobType._commit_install

    def commit_then_fail(self, job, applications):
        commit_install(self, job, applications)
        assert job.installed_applications
        raise RuntimeError("Failed before the transaction committed")

    with (
        patch.object(InstallTemplateJobType, "_commit_install", commit_then_fail),
        pytest.raises(RuntimeError),
    ):
        _run(job)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    # The ids of the rolled back applications aren't saved with the failure.
    assert job.installed_applications == []
    _assert_nothing_installed(target, root, counts)


@install_marks
@pytest.mark.parametrize(
    "exception", [RuntimeError("Clean-up failed"), SoftTimeLimitExceeded()]
)
def test_install_user_template_job_fails_after_the_commit(data_fixture, exception):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)

    with patch(
        "baserow.core.user_templates.handler._mark_resource_for_deletion",
        side_effect=exception,
    ) as mark_resource_for_deletion:
        job = _run(job)

    mark_resource_for_deletion.assert_called_once()
    # The install is committed, so a failure after it doesn't undo it.
    assert job.state == JOB_FINISHED
    applications = list(
        Application.objects.filter(workspace=target).order_by("order", "id")
    )
    assert [app.name for app in applications] == ["First", "Second"]
    assert job.installed_applications == [app.id for app in applications]
    assert Template.objects.get(id=root.id).install_count == 1


@install_marks
def test_install_user_template_job_soft_time_limit(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    with _import_application_raising(SoftTimeLimitExceeded()):
        job = _run(job)

    assert job.state == JOB_FAILED
    assert job.error_code == "SoftTimeLimitExceeded"
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_cancelled_before_it_starts(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    JobHandler.cancel_job(job)
    job = _run(job)

    assert job.state == JOB_CANCELLED
    _assert_nothing_installed(target, root, counts)
    assert not ImportExportResource.objects.exists()


@install_marks
def test_install_user_template_job_cancelled_during_the_import(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner, names=("First", "Second", "Third"))
    job = _request_install(owner, target, root)
    counts = _counts()

    def cancel():
        JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))

    with _import_application_raising(None, before=cancel):
        job = _run(job)

    assert job.state == JOB_CANCELLED
    assert job.installed_applications == []
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_cancelled_at_the_commit_point(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()
    commit_install = InstallTemplateJobType._commit_install

    def cancel_then_commit(self, job, applications):
        JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
        # A progress update that read the cache before the cancel writes the
        # state of the worker back, so only the locked row knows.
        job.set_cached_state()
        commit_install(self, job, applications)

    with patch.object(InstallTemplateJobType, "_commit_install", cancel_then_commit):
        job = _run(job)

    assert job.state == JOB_CANCELLED
    assert job.installed_applications == []
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_cannot_be_cancelled_after_the_commit(
    data_fixture,
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    commit_install = InstallTemplateJobType._commit_install

    def commit_then_cancel(self, job, applications):
        commit_install(self, job, applications)
        with pytest.raises(JobNotCancellable):
            JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))

    with patch.object(InstallTemplateJobType, "_commit_install", commit_then_cancel):
        job = _run(job)

    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 1
    with pytest.raises(JobNotCancellable):
        JobHandler.cancel_job(job)


@install_marks
def test_install_user_template_job_concurrent_cancel_waits_for_the_commit(
    data_fixture, test_thread
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    commit_install = InstallTemplateJobType._commit_install
    outcome = {}

    def cancel():
        try:
            JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
            outcome["cancel"] = "accepted"
        except JobNotCancellable:
            outcome["cancel"] = "refused"
        finally:
            connection.close()

    with test_thread(cancel) as thread:

        def commit_with_a_concurrent_cancel(self, job, applications):
            commit_install(self, job, applications)
            thread.start()
            # The cancel waits for the lock that the job holds until it commits.
            assert not thread.thread_stopped.wait(0.3)

        with patch.object(
            InstallTemplateJobType, "_commit_install", commit_with_a_concurrent_cancel
        ):
            job = _run(job)

    assert outcome == {"cancel": "refused"}
    assert job.state == JOB_FINISHED
    assert Template.objects.get(id=root.id).install_count == 1


@install_marks
def test_install_user_template_job_max_locks_in_the_import(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    with _import_application_raising(
        OperationalError("HINT:  You might need to increase max_locks_per_transaction.")
    ):
        job = _run(job)

    assert job.state == JOB_FAILED
    assert job.error_code == "InstallTemplateMaxLocksExceededException"
    assert job.human_readable_error == (
        "Baserow attempted to install a template, but exceeded the maximum number "
        "of PostgreSQL locks per transaction. Please read "
        "https://baserow.io/docs/technical/postgresql-locks"
    )
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_max_locks_in_the_export(
    data_fixture, application_type_serialized_raising_operationalerror
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    with application_type_serialized_raising_operationalerror():
        job = _run(job)

    assert job.state == JOB_FAILED
    assert job.error_code == "InstallTemplateMaxLocksExceededException"
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_job_other_operational_error_isnt_mapped(
    data_fixture, application_type_serialized_raising_operationalerror
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    counts = _counts()

    with (
        application_type_serialized_raising_operationalerror(
            raise_transaction_exception=False
        ),
        pytest.raises(OperationalError),
    ):
        _run(job)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error_code == ""
    _assert_nothing_installed(target, root, counts)


@install_marks
def test_install_user_template_leaves_the_template_unchanged(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    revision = data_fixture.create_user_template_revision(root)
    _add_database(data_fixture, revision.workspace, "Latest")

    def snapshot():
        templates = {
            row["id"]: row
            for row in Template.objects.filter(id__in=[root.id, revision.id]).values()
        }
        templates[root.id].pop("install_count")
        applications = list(
            Application.objects_and_trash.filter(
                workspace_id__in=[root.workspace_id, revision.workspace_id]
            )
            .order_by("id")
            .values()
        )
        rows = [
            list(app.specific.table_set.get().get_model().objects.values())
            for app in Application.objects.filter(
                workspace_id__in=[root.workspace_id, revision.workspace_id]
            ).order_by("id")
        ]
        return templates, applications, rows

    before = snapshot()
    job = _install(owner, target, root)

    assert job.state == JOB_FINISHED
    assert snapshot() == before


@install_marks
def test_installed_applications_are_independent_of_the_template(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _install(owner, target, root)
    installed = list(
        Application.objects.filter(workspace=target).order_by("id").values()
    )

    revision = data_fixture.create_user_template_revision(root)
    _add_database(data_fixture, revision.workspace, "Updated")
    Application.objects.filter(workspace=root.workspace).update(name="Renamed")

    assert (
        list(Application.objects.filter(workspace=target).order_by("id").values())
        == installed
    )

    Template.objects.filter(id=root.id).update(public_revision=None)
    root.delete()

    applications = Application.objects.filter(workspace=target)
    assert sorted(applications.values_list("id", flat=True)) == sorted(
        job.installed_applications
    )
    assert set(applications.values_list("installed_from_template", flat=True)) == {None}


@install_marks
def test_install_user_template_schedules_search_data_of_installed_tables(
    data_fixture,
):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)

    with patch.object(SearchHandler, "schedule_update_search_data") as schedule:
        job = _install(owner, target, root)

    assert job.state == JOB_FINISHED
    # Like the official install, so that search works in the copy right away.
    installed_tables = {
        table.id
        for application in Application.objects.filter(workspace=target)
        for table in application.specific.table_set.all()
    }
    assert len(installed_tables) == 2
    assert {call.args[0].id for call in schedule.call_args_list} == installed_tables


def _delete(user, root):
    """Deletes the template, and lets the grace period of its removal pass."""

    DeleteUserTemplateActionType.do(user, root.id)
    Template.objects.filter(id=root.id).update(
        marked_for_deletion_at=timezone.now()
        - USER_TEMPLATE_DELETION_GRACE_PERIOD
        - timedelta(hours=1)
    )


def _purge():
    UserTemplateHandler().delete_marked_templates()


def _assert_removed_and_installed_copy_kept(root, target, job):
    assert not Template.objects.filter(Q(id=root.id) | Q(root_id=root.id)).exists()
    assert not InstallTemplateJob.objects.filter(id=job.id).exists()
    applications = Application.objects.filter(workspace=target)
    assert sorted(applications.values_list("id", flat=True)) == sorted(
        job.installed_applications
    )
    assert set(applications.values_list("installed_from_template", flat=True)) == {None}


@install_marks
def test_deleted_template_is_removed_after_a_requested_install(data_fixture):
    owner = data_fixture.create_user()
    viewer = data_fixture.create_user()
    target = data_fixture.create_workspace(user=viewer)
    root = _create_template(data_fixture, owner)
    job = _request_install(viewer, target, root)

    _delete(owner, root)

    # A new install is refused, the requested one waits in the queue, and the
    # template waits for it.
    with pytest.raises(TemplateDoesNotExist):
        _request_install(viewer, target, root)
    _purge()
    assert Template.objects.filter(id=root.id).exists()

    job = _run(job)
    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]

    _purge()

    _assert_removed_and_installed_copy_kept(root, target, job)


@install_marks
def test_deleted_template_is_removed_after_a_running_install(data_fixture, test_thread):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner)
    job = _request_install(owner, target, root)
    kept_while_running = []

    # Outside of the transaction of the install, like a request and the cleanup
    # task.
    def delete_and_purge_in_another_connection():
        try:
            _delete(owner, root)
            _purge()
        finally:
            connection.close()

    def delete_and_purge():
        with test_thread(delete_and_purge_in_another_connection) as thread:
            thread.start()
            assert thread.thread_stopped.wait(30)
        kept_while_running.append(Template.objects.filter(id=root.id).exists())

    with _import_application_raising(None, before=delete_and_purge):
        job = _run(job)

    assert kept_while_running == [True]
    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]

    _purge()

    _assert_removed_and_installed_copy_kept(root, target, job)


# The official install runs in the transaction of the job, so it's rolled back
# when it's cancelled, and `is_cancellable` keeps it cancellable until it ends.


@pytest.mark.django_db(transaction=True)
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_official_install_cancelled_before_it_starts(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    CoreHandler().sync_templates()
    template = Template.objects.get(slug="example-template")
    job = _request_install(user, workspace, template)

    JobHandler.cancel_job(job)
    job = _run(job)

    assert job.state == JOB_CANCELLED
    assert not Application.objects_and_trash.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_official_install_cancelled_while_it_runs(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    CoreHandler().sync_templates()
    template = Template.objects.get(slug="example-template")
    job = _request_install(user, workspace, template)
    install_template = CoreHandler.install_template

    def install_then_cancel(self, *args, **kwargs):
        result = install_template(self, *args, **kwargs)
        assert Application.objects.filter(workspace=workspace).exists()
        # The cancellation of another request, which commits.
        with django_capture_on_commit_callbacks(execute=True):
            JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
        return result

    with patch.object(CoreHandler, "install_template", install_then_cancel):
        job = _run(job)

    assert job.state == JOB_CANCELLED
    assert not Application.objects_and_trash.filter(workspace=workspace).exists()
    assert Template.objects.get(id=template.id).install_count == 0


@pytest.mark.django_db
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_install_job_with_installed_applications_isnt_cancellable(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    CoreHandler().sync_templates()
    template = Template.objects.get(slug="example-template")
    job = _request_install(user, workspace, template)
    job.set_state_started()
    job.save()
    InstallTemplateJob.objects.filter(id=job.id).update(installed_applications=[1])

    with pytest.raises(JobNotCancellable):
        JobHandler.cancel_job(job)

    assert InstallTemplateJob.objects.get(id=job.id).state != JOB_CANCELLED
