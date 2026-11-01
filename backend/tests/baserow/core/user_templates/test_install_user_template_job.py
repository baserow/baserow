import os
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import OperationalError
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.database.fields.rich_text_utils import extract_user_file_names
from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.action.models import Action
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import (
    Application,
    ImportExportResource,
    InstallTemplateJob,
    Template,
    TrashEntry,
    UserFile,
    WorkspaceUser,
)
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_templates.actions import DeleteUserTemplateActionType
from tests.baserow.core.user_templates.utils import (
    add_password_data,
    assert_password_data_left_out,
    cancel_in_another_connection,
    fail_on_import,
    install,
    install_marks,
    long_ago,
    purge,
    request_install,
    run_job,
)

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")


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
    data_fixture.set_user_template_state(root, "public", revisions[1])
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


def _create_template(data_fixture, owner, names=("First", "Second")):
    """
    A user template of the owner, public, with a database per name in its
    workspace, each with a table and a row.
    """

    root = data_fixture.create_user_template(user=owner, name="Mine")
    for name in names:
        data_fixture.create_template_table(root.workspace, name, f"{name} row")
    return data_fixture.set_user_template_state(root, "public")


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


def _queue_install(data_fixture, names=("First", "Second")):
    """
    The owner of a public user template with a database per name, a workspace
    of the owner to install it into, and an install of it waiting in the queue.
    """

    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner, names)
    job = request_install(owner, target, root)
    return SimpleNamespace(
        owner=owner, target=target, root=root, job=job, counts=_counts()
    )


@pytest.fixture
def queued_install(data_fixture):
    return _queue_install(data_fixture)


@install_marks
def test_install_user_template_job(data_fixture, queued_install):
    owner, target, root = (
        queued_install.owner,
        queued_install.target,
        queued_install.root,
    )
    updated_on = root.updated_on

    job = run_job(queued_install.job)

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
    # The content is copied directly, without an export.
    assert not ImportExportResource.objects_and_trash.exists()

    # Each install is counted on the root, whatever revision it installs.
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    data_fixture.create_template_table(revision.workspace, "Latest", "Latest row")
    latest_target = data_fixture.create_workspace(user=owner)
    assert install(owner, latest_target, root, latest=True).template_id == revision.id
    assert _installed_names(latest_target) == ["Latest"]
    assert Template.objects.get(id=root.id).install_count == 2
    assert Template.objects.get(id=revision.id).install_count == 0


@install_marks
def test_install_user_template_empties_password_fields(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = _create_template(data_fixture, owner, names=["First"])
    template_table = root.workspace.application_set.get().specific.table_set.get()
    # Set in the template workspace directly, like a template made before its
    # passwords were left out.
    password_field, password = add_password_data(
        data_fixture,
        template_table,
        data_fixture.create_grid_view(table=template_table),
    )

    job = install(owner, target, root)

    assert job.state == JOB_FINISHED
    installed = Application.objects.get(workspace=target).specific
    assert_password_data_left_out(installed.table_set.get())
    # The template keeps what it holds.
    assert list(
        template_table.get_model().objects.values_list(
            password_field.db_column, flat=True
        )
    ) == [password]


@install_marks
def test_install_pinned_revision_survives_an_update(data_fixture, queued_install):
    target, root = queued_install.target, queued_install.root

    # A content update is approved and made public while the install waits in
    # the queue.
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    data_fixture.create_template_table(revision.workspace, "Updated", "Updated row")
    Template.objects.filter(id=root.id).update(public_revision=revision)

    job = run_job(queued_install.job)

    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]
    assert set(
        Application.objects.filter(workspace=target).values_list(
            "installed_from_template_id", flat=True
        )
    ) == {root.id}


def _refused_after_request(data_fixture, flip, installer="owner"):
    """
    Requests an install, flips something with `flip(context)` before the job
    runs, then runs it.
    """

    owner = data_fixture.create_user()
    user = owner if installer == "owner" else data_fixture.create_user()
    target = data_fixture.create_workspace(user=user)
    root = _create_template(data_fixture, owner)
    job = request_install(user, target, root)
    counts = _counts()

    flip({"root": root, "user": user, "target": target})

    return run_job(job), target, root, counts


def _block(context):
    Template.objects.filter(id=context["root"].id).update(blocked_at=timezone.now())


def _make_private(context):
    Template.objects.filter(id=context["root"].id).update(public_revision=None)


def _remove_from_target(context):
    WorkspaceUser.objects.filter(
        user=context["user"], workspace=context["target"]
    ).delete()


@pytest.mark.parametrize(
    "installer,flip,error_code",
    [
        ("owner", _block, "TemplateBlocked"),
        ("viewer", _make_private, "TemplateDoesNotExist"),
        ("viewer", _block, "TemplateDoesNotExist"),
        ("owner", _remove_from_target, "UserNotInWorkspace"),
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


@install_marks
def test_install_user_template_job_fails_on_import_of_second_application(
    queued_install,
):
    job = queued_install.job

    with (
        fail_on_import(RuntimeError("Import failed")),
        pytest.raises(RuntimeError),
    ):
        run_job(job)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.installed_applications == []
    _assert_nothing_installed(
        queued_install.target, queued_install.root, queued_install.counts
    )


@install_marks
def test_install_user_template_job_cancelled_during_the_import(data_fixture):
    queued = _queue_install(data_fixture, names=("First", "Second", "Third"))

    def cancel():
        JobHandler.cancel_job(InstallTemplateJob.objects.get(id=queued.job.id))

    with fail_on_import(None, before=cancel):
        job = run_job(queued.job)

    assert job.state == JOB_CANCELLED
    assert job.installed_applications == []
    _assert_nothing_installed(queued.target, queued.root, queued.counts)


@install_marks
def test_install_user_template_job_cancelled_at_the_commit_point(queued_install):
    commit_install = InstallTemplateJobType._commit_install

    def cancel_then_commit(self, job, applications):
        JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
        # A progress update that read the cache before the cancel writes the
        # state of the worker back, so only the locked row knows.
        job.set_cached_state()
        commit_install(self, job, applications)

    with patch.object(InstallTemplateJobType, "_commit_install", cancel_then_commit):
        job = run_job(queued_install.job)

    assert job.state == JOB_CANCELLED
    assert job.installed_applications == []
    _assert_nothing_installed(
        queued_install.target, queued_install.root, queued_install.counts
    )


@install_marks
def test_install_user_template_job_concurrent_cancel_waits_for_the_commit(
    queued_install, test_thread
):
    job = queued_install.job
    commit_install = InstallTemplateJobType._commit_install
    outcome = {}

    with test_thread(
        cancel_in_another_connection, outcome, InstallTemplateJob, id=job.id
    ) as thread:

        def commit_with_a_concurrent_cancel(self, job, applications):
            commit_install(self, job, applications)
            thread.start()
            # The cancel waits for the lock that the job holds until it commits.
            assert not thread.thread_stopped.wait(0.3)

        with patch.object(
            InstallTemplateJobType, "_commit_install", commit_with_a_concurrent_cancel
        ):
            job = run_job(job)

    assert outcome == {"cancel": "refused"}
    assert job.state == JOB_FINISHED
    assert _installed_names(queued_install.target) == ["First", "Second"]
    assert Template.objects.get(id=queued_install.root.id).install_count == 1
    # A finished install can't be cancelled either.
    with pytest.raises(JobNotCancellable):
        JobHandler.cancel_job(job)


@install_marks
def test_install_user_template_job_max_locks_in_the_import(queued_install):
    with fail_on_import(
        OperationalError("HINT:  You might need to increase max_locks_per_transaction.")
    ):
        job = run_job(queued_install.job)

    assert job.state == JOB_FAILED
    assert job.error_code == "InstallTemplateMaxLocksExceededException"
    assert job.human_readable_error == (
        "Baserow attempted to install a template, but exceeded the maximum number "
        "of PostgreSQL locks per transaction. Please read "
        "https://baserow.io/docs/technical/postgresql-locks"
    )
    _assert_nothing_installed(
        queued_install.target, queued_install.root, queued_install.counts
    )


@install_marks
def test_install_user_template_leaves_the_template_unchanged(
    data_fixture, queued_install
):
    root = queued_install.root
    revision = data_fixture.create_user_template_revision(root)
    data_fixture.create_template_table(revision.workspace, "Latest", "Latest row")

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
    job = run_job(queued_install.job)

    assert job.state == JOB_FINISHED
    assert snapshot() == before


@install_marks
def test_installed_applications_are_independent_of_the_template(
    data_fixture, queued_install
):
    target, root = queued_install.target, queued_install.root
    job = run_job(queued_install.job)
    installed = list(
        Application.objects.filter(workspace=target).order_by("id").values()
    )

    revision = data_fixture.create_user_template_revision(root)
    data_fixture.create_template_table(revision.workspace, "Updated", "Updated row")
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
    queued_install,
):
    with patch.object(SearchHandler, "schedule_update_search_data") as schedule:
        job = run_job(queued_install.job)

    assert job.state == JOB_FINISHED
    # Like the official install, so that search works in the copy right away.
    installed_tables = {
        table.id
        for application in Application.objects.filter(workspace=queued_install.target)
        for table in application.specific.table_set.all()
    }
    assert len(installed_tables) == 2
    assert {call.args[0].id for call in schedule.call_args_list} == installed_tables


def _delete(user, root):
    """Deletes the template, and lets the grace period of its removal pass."""

    DeleteUserTemplateActionType.do(user, root.id)
    Template.objects.filter(id=root.id).update(marked_for_deletion_at=long_ago())


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
    job = request_install(viewer, target, root)

    _delete(owner, root)

    # A new install is refused, the requested one waits in the queue, and the
    # template waits for it.
    with pytest.raises(TemplateDoesNotExist):
        request_install(viewer, target, root)
    purge()
    assert Template.objects.filter(id=root.id).exists()

    job = run_job(job)
    assert job.state == JOB_FINISHED
    assert _installed_names(target) == ["First", "Second"]
    assert Template.objects.get(id=root.id).install_count == 1

    purge()

    _assert_removed_and_installed_copy_kept(root, target, job)


def _add_files(data_fixture, owner, workspace):
    """
    A database with a row holding an uploaded file in a file field and an image
    in a rich text field.
    """

    database = data_fixture.create_database_application(
        workspace=workspace, name="Files"
    )
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True, name="Name")
    file_field = data_fixture.create_file_field(table=table, name="File")
    notes_field = data_fixture.create_long_text_field(
        table=table, name="Notes", long_text_enable_rich_text=True
    )
    handler = UserFileHandler()
    document = handler.upload_user_file(owner, "document.txt", ContentFile(b"Document"))
    image = handler.upload_user_file(owner, "photo.png", ContentFile(b"Photo"))
    table.get_model().objects.create(
        **{
            file_field.db_column: [
                {**document.serialize(), "visible_name": "document.txt"}
            ],
            notes_field.db_column: f"Look ![photo][{image.name}] here",
        }
    )
    return SimpleNamespace(document=document, image=image)


def _installed_files(workspace):
    """The names of the user files of the row installed by `_add_files`."""

    table = Application.objects.get(workspace=workspace).specific.table_set.get()
    fields = {field.name: field for field in table.field_set.all()}
    row = table.get_model().objects.get()
    return SimpleNamespace(
        documents=[file["name"] for file in getattr(row, fields["File"].db_column)],
        images=sorted(extract_user_file_names(getattr(row, fields["Notes"].db_column))),
    )


def _read_user_file(name):
    with get_default_storage().open(UserFileHandler().user_file_path(name)) as f:
        return f.read()


@install_marks
def test_installed_copy_keeps_its_files_after_the_template_is_deleted(data_fixture):
    owner = data_fixture.create_user()
    target = data_fixture.create_workspace(user=owner)
    root = data_fixture.create_user_template(user=owner, name="Mine")
    files = _add_files(data_fixture, owner, root.workspace)
    data_fixture.set_user_template_state(root, "public")

    job = install(owner, target, root)
    _delete(owner, root)
    purge()

    assert job.state == JOB_FINISHED
    _assert_removed_and_installed_copy_kept(root, target, job)
    # Like a duplicate, the copy refers to the user files of the template, which
    # the purge of the template keeps.
    installed = _installed_files(target)
    assert installed.documents == [files.document.name]
    assert UserFile.objects.all().name(files.document.name).exists()
    assert _read_user_file(files.document.name) == b"Document"
    assert installed.images == [files.image.name]
    assert _read_user_file(files.image.name) == b"Photo"


# The official install runs in the transaction of the job, so it's rolled back
# when it's cancelled, and `is_cancellable` keeps it cancellable until it ends.
@pytest.mark.django_db(transaction=True)
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_official_install_cancelled_while_it_runs(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    CoreHandler().sync_templates()
    template = Template.objects.get(slug="example-template")
    job = request_install(user, workspace, template)
    install_template = CoreHandler.install_template

    def install_then_cancel(self, *args, **kwargs):
        result = install_template(self, *args, **kwargs)
        assert Application.objects.filter(workspace=workspace).exists()
        # The cancellation of another request, which commits.
        with django_capture_on_commit_callbacks(execute=True):
            JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
        return result

    with patch.object(CoreHandler, "install_template", install_then_cancel):
        job = run_job(job)

    assert job.state == JOB_CANCELLED
    assert not Application.objects_and_trash.filter(workspace=workspace).exists()
    assert Template.objects.get(id=template.id).install_count == 0
