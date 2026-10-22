from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone as django_timezone

import pytest

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowIntegration,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.cache import local_cache
from baserow.core.exceptions import (
    PermissionDenied,
    TemplateDoesNotExist,
    UserNotInWorkspace,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
)
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import Job
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import Template, TemplateCategory, Workspace, WorkspaceUser
from baserow.core.operations import ExportWorkspaceOperationType
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.actions import (
    DeleteUserTemplateActionType,
    UpdateUserTemplateActionType,
)
from baserow.core.user_templates.constants import USER_TEMPLATE_DELETION_GRACE_PERIOD
from baserow.core.user_templates.exceptions import (
    InvalidTemplateCategory,
    InvalidTemplateIcon,
    TemplateChangedDuringUpdate,
    TemplateHasNoContent,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow.core.user_templates.models import CreateUserTemplateJob
from baserow.core.user_templates.service import UserTemplateService
from baserow.core.user_templates.tasks import delete_orphaned_user_template_workspaces
from tests.baserow.core.user_templates.utils import (
    CLEARED_KEYS,
    ICON,
    another_run_after_the_copy,
    copied_applications,
    create_source,
    find_values,
    read_archive,
    run_again,
    start_job,
)

OTHER_ICON = "iconoir-calendar"


def update_details(user, template, **kwargs):
    kwargs.setdefault("name", "Renamed")
    kwargs.setdefault("description", "What it does now")
    kwargs.setdefault("icon", OTHER_ICON)
    if "category_ids" not in kwargs:
        kwargs["category_ids"] = [TemplateCategory.objects.create(name="New").id]
    return JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        template_id=template.id,
        **kwargs,
    )


def update_content(user, template, workspace, applications, **kwargs):
    return JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        template_id=template.id,
        workspace_id=workspace.id,
        application_ids=[application.id for application in applications],
        **kwargs,
    )


def create_template(data_fixture, user, **kwargs):
    """A user template whose content can be copied, without running a job."""

    workspace = data_fixture.create_workspace(name="Content")
    data_fixture.create_database_application(workspace=workspace)
    kwargs.setdefault("icon", ICON)
    return data_fixture.create_user_template(user=user, workspace=workspace, **kwargs)


def revisions_of(root):
    return list(
        Template.objects.filter(root=root)
        .order_by("version")
        .values_list("version", flat=True)
    )


def assert_no_job_content_left(job):
    assert job.template_workspace_id is None or not (
        Workspace.objects_and_trash.filter(id=job.template_workspace_id).exists()
    )
    if job.archive_name:
        assert not get_default_storage().exists(job.archive_name)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_details(data_fixture, use_tmp_media_root):
    source = create_source(data_fixture)
    user = source["user"]
    applications = [
        source["database"],
        source["builder"],
        source["dashboard"],
        source["automation"],
    ]
    root = start_job(user, source["workspace"], applications, name="Mine").template
    root.private_link_token = "secret-token"
    root.review_state = Template.ReviewState.APPROVED
    root.public_revision = root
    root.save()
    root_before = Template.objects.get(id=root.id)
    category = data_fixture.create_template_category()
    workspace_count = Workspace.objects_and_trash.count()

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        job = update_details(
            user,
            root,
            name="Renamed",
            description="",
            icon=OTHER_ICON,
            category_ids=[category.id],
        )

    assert job.state == JOB_FINISHED, job.error
    job.refresh_from_db()
    revision = Template.objects.get(root=root)
    assert job.template_id == root.id
    assert job.revision_id == revision.id
    assert job.base_revision_id == root.id
    assert job.source_workspace_id is None
    assert job.application_ids == []
    assert job.template_workspace_id is None
    assert not job.archive_name

    assert revision.version == 2
    assert revision.type == Template.Type.USER
    assert revision.slug == ""
    assert revision.name == "Renamed"
    assert revision.description == ""
    assert revision.icon == OTHER_ICON
    assert list(revision.categories.all()) == [category]
    assert revision.metadata == root.metadata
    assert revision.review_state == Template.ReviewState.NOT_SUBMITTED
    revision.full_clean(exclude=["open_application"])

    # The content of the root is shared, not copied, so that a details-only
    # revision can be told apart from a content change.
    assert revision.workspace_id == root.workspace_id
    assert revision.archive.name == root.archive.name
    assert Workspace.objects_and_trash.count() == workspace_count
    assert revision.workspace.name == root_before.workspace.name
    # The template types of a workspace are cached by `updated_on`, so it changes
    # once the revision points at it.
    assert revision.workspace.updated_on >= revision.created_on
    assert set(copied_applications(revision)) == {
        "database",
        "builder",
        "dashboard",
        "automation",
    }
    assert get_default_storage().exists(root.archive.name)

    root.refresh_from_db()
    for field_name in [
        "slug",
        "private_link_token",
        "owner_id",
        "author_id",
        "public_revision_id",
        "name",
        "icon",
        "workspace_id",
    ]:
        assert getattr(root, field_name) == getattr(root_before, field_name)
    assert root.updated_on > root_before.updated_on

    action_done.assert_called_once()
    action_kwargs = action_done.call_args.kwargs
    assert action_kwargs["action_type"].type == "update_user_template"
    assert action_kwargs["workspace"] is None
    assert action_kwargs["action_params"] == {
        "template_id": root.id,
        "template_name": "Renamed",
        "revision_id": revision.id,
        "version": 2,
        "workspace_id": None,
        "workspace_name": None,
        "application_ids": None,
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_content(data_fixture, use_tmp_media_root):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]
    category = data_fixture.create_template_category()
    root = start_job(
        user,
        workspace,
        [source["database"]],
        name="Mine",
        description="Kept",
        category_ids=[category.id],
    ).template
    applications = [source["database"], source["dashboard"]]

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        job = update_content(user, root, workspace, applications)

    assert job.state == JOB_FINISHED, job.error
    revision = Template.objects.get(root=root)
    assert job.revision_id == revision.id
    assert revision.version == 2
    assert revision.metadata == {
        "source_workspace_id": workspace.id,
        "source_application_ids": [application.id for application in applications],
    }
    assert revision.name == "Mine"
    assert revision.description == "Kept"
    assert revision.icon == ICON
    assert list(revision.categories.all()) == [category]
    assert set(copied_applications(revision)) == {"database", "dashboard"}
    assert set(copied_applications(root)) == {"database"}

    action_done.assert_called_once()
    action_kwargs = action_done.call_args.kwargs
    assert action_kwargs["action_type"].type == "update_user_template"
    assert action_kwargs["workspace"] == workspace
    assert action_kwargs["action_params"] == {
        "template_id": root.id,
        "template_name": "Mine",
        "revision_id": revision.id,
        "version": 2,
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "application_ids": [application.id for application in applications],
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_content_rules(data_fixture, use_tmp_media_root):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]
    applications = [source["builder"], source["dashboard"], source["automation"]]
    root = start_job(user, workspace, applications).template

    # A details-only update shares the content, which followed the rules when it
    # was copied.
    job = update_content(user, root, workspace, applications)

    assert job.state == JOB_FINISHED, job.error
    revision = Template.objects.get(root=root)
    assert not WorkspaceUser.objects.filter(workspace=revision.workspace).exists()
    copied = copied_applications(revision)
    integrations = LocalBaserowIntegration.objects.filter(
        application__in=[copied["builder"], copied["dashboard"]]
    )
    assert len(integrations) == 2
    for integration in integrations:
        assert integration.authorized_subject_id is None
    smtp = SMTPIntegration.objects.get(application=copied["automation"])
    assert not smtp.username
    assert not smtp.password
    # The database wasn't selected, so nothing points outside the template.
    services = [
        data_source.service.specific
        for data_source in DataSource.objects.filter(page__builder=copied["builder"])
    ] + list(
        LocalBaserowAggregateRows.objects.filter(
            dashboard_data_source__dashboard=copied["dashboard"]
        )
    )
    assert len(services) == 3
    for service in services:
        assert service.table_id is None
        assert service.view_id is None
    archive = read_archive(revision.archive.name)
    assert archive
    for key, value in find_values(archive, CLEARED_KEYS):
        assert value in (None, ""), f"{key} = {value}"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_details_of_a_later_revision(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(name="Revision 2")
    data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_application(workspace=workspace)
    revision_2 = data_fixture.create_user_template_revision(
        root,
        icon=ICON,
        workspace=workspace,
        metadata={"source_workspace_id": 1, "other": "dropped"},
    )

    job = update_details(user, root)

    assert job.state == JOB_FINISHED, job.error
    assert job.base_revision_id == revision_2.id
    assert revisions_of(root) == [2, 3]
    revision_3 = Template.objects.get(root=root, version=3)
    assert revision_3.metadata == {"source_workspace_id": 1}
    assert revision_3.workspace.application_set.count() == 2


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_job_redelivered_after_its_commit_isnt_run_again(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    job = update_details(user, root)

    again = run_again(job.id)

    assert again.state == JOB_FINISHED, again.error
    assert again.revision_id == job.revision_id
    assert revisions_of(root) == [2]


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_job_keeps_the_commit_of_another_run(
    data_fixture, use_tmp_media_root
):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]
    root = start_job(user, workspace, [source["database"]]).template

    with another_run_after_the_copy() as other_runs:
        job = update_content(user, root, workspace, [source["database"]])

    revision = Template.objects.get(root=root)
    assert job.state == JOB_FINISHED, job.error
    assert job.revision_id == other_runs[0].revision_id == revision.id
    assert job.template_workspace_id == revision.workspace_id
    assert job.archive_name == revision.archive.name
    assert revisions_of(root) == [2]
    assert set(Workspace.objects_and_trash.all()) == {
        workspace,
        root.workspace,
        revision.workspace,
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_blocked_template(data_fixture, use_tmp_media_root):
    user = data_fixture.create_user()
    root = create_template(
        data_fixture,
        user,
        blocked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        blocked_reason="Spam",
    )

    job = update_details(user, root)

    assert job.state == JOB_FINISHED, job.error
    assert revisions_of(root) == [2]


@pytest.mark.django_db
def test_update_user_template_refuses_templates_not_owned(data_fixture):
    owner = data_fixture.create_user()
    root = create_template(data_fixture, owner)
    revision = data_fixture.create_user_template_revision(root, icon=ICON)
    marked = create_template(
        data_fixture, owner, marked_for_deletion_at=django_timezone.now()
    )
    official = data_fixture.create_template(icon=ICON)

    for user, template in [
        (data_fixture.create_user(), root),
        (data_fixture.create_user(is_staff=True), root),
        (owner, marked),
        (owner, official),
        (owner, revision),
    ]:
        with pytest.raises(TemplateDoesNotExist):
            update_details(user, template)

    assert not CreateUserTemplateJob.objects.exists()
    assert revisions_of(root) == [2]


DETAILS = {"name": "Renamed", "description": "", "icon": ICON, "category_ids": [1]}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values,fields",
    [
        # Updating the details forbids applications.
        ({**DETAILS, "application_ids": [1]}, ["application_ids"]),
        ({"icon": ICON, "category_ids": [1]}, ["name", "description"]),
        # Updating the content keeps the details of the latest revision.
        (
            {"workspace_id": 1, "application_ids": [1], "name": "x", "icon": ICON},
            ["name", "icon"],
        ),
        ({"workspace_id": 1}, ["application_ids"]),
    ],
)
def test_update_user_template_request_modes(data_fixture, values, fields):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)

    with pytest.raises(RequestBodyValidationException) as exc_info:
        JobHandler().create_and_start_job(
            user, CreateUserTemplateJobType.type, template_id=root.id, **values
        )

    assert sorted(exc_info.value.detail["detail"]) == sorted(fields)
    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values,error",
    [
        ({"icon": "not-an-icon"}, InvalidTemplateIcon),
        ({"category_ids": [999999]}, InvalidTemplateCategory),
    ],
)
def test_update_user_template_details_with_invalid_icon_or_category(
    data_fixture, values, error
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)

    # Refused before the content is copied.
    with pytest.raises(error):
        update_details(user, root, **values)

    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,error",
    [("icon", InvalidTemplateIcon), ("categories", InvalidTemplateCategory)],
)
def test_update_user_template_content_with_invalid_kept_details(
    data_fixture, change, error
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    root = create_template(data_fixture, user)
    if change == "icon":
        Template.objects.filter(id=root.id).update(icon="not-an-icon")
    else:
        root.categories.all().delete()
        # Another category exists, so the template needs one.
        TemplateCategory.objects.create(name="Other")

    # The kept details are refused before the content is copied, because the user
    # can't change them in this mode.
    with pytest.raises(error):
        update_content(user, root, workspace, [database])

    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
def test_update_user_template_content_refuses_foreign_content(data_fixture):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    other_workspace = data_fixture.create_workspace(user=user)
    foreign = data_fixture.create_database_application(workspace=other_workspace)
    stranger_workspace = data_fixture.create_workspace()
    stranger_database = data_fixture.create_database_application(
        workspace=stranger_workspace
    )
    template_workspace = data_fixture.create_workspace(user=user)
    template_database = data_fixture.create_database_application(
        workspace=template_workspace
    )
    data_fixture.create_template(workspace=template_workspace)

    with pytest.raises(PermissionDenied):
        update_content(user, root, workspace, [database, foreign])
    with pytest.raises(UserNotInWorkspace):
        update_content(user, root, stranger_workspace, [stranger_database])
    with pytest.raises(UserNotInWorkspace):
        update_content(user, root, root.workspace, root.workspace.application_set.all())
    with pytest.raises(PermissionDenied):
        update_content(user, root, template_workspace, [template_database])

    assert not CreateUserTemplateJob.objects.exists()


def change_before_the_job_runs(change):
    """Calls `change` while the job waits for a worker, before it runs."""

    run = CreateUserTemplateJobType.run

    def change_then_run(self, job, progress):
        change()
        # The job runs in its own worker, without what this test has cached.
        local_cache.clear()
        job.refresh_from_db()
        return run(self, job, progress)

    return patch.object(CreateUserTemplateJobType, "run", change_then_run)


def update_while_changing(data_fixture, user, root, mode, change, **kwargs):
    """
    Updates `root` and calls `change` once its content is ready, right before the
    revision is committed: after the copy of a content update, or after getting
    the shared content of a details-only update.
    """

    if mode == "details":
        get_template_content = UserTemplateService.get_template_content
        run = CreateUserTemplateJobType.run

        def get_then_change(self, *args, **kw):
            content = get_template_content(self, *args, **kw)
            change()
            return content

        # Only while the job runs, because the request is checked with it too.
        def run_with_change(self, job, progress):
            with patch.object(
                UserTemplateService, "get_template_content", get_then_change
            ):
                return run(self, job, progress)

        with patch.object(CreateUserTemplateJobType, "run", run_with_change):
            return update_details(user, root, **kwargs)

    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    copy_applications = UserTemplateHandler.copy_applications

    def copy_then_change(self, *args, **kw):
        content = copy_applications(self, *args, **kw)
        change()
        return content

    with patch.object(UserTemplateHandler, "copy_applications", copy_then_change):
        return update_content(user, root, workspace, [database], **kwargs)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("loss", ["membership", "export_permission"])
def test_update_user_template_content_fails_when_access_is_lost_before_it_runs(
    data_fixture, use_tmp_media_root, loss
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    check_permissions = CoreHandler.check_permissions

    def deny_export(self, actor, operation_name, *args, **kwargs):
        if operation_name == ExportWorkspaceOperationType.type:
            raise PermissionDenied()
        return check_permissions(self, actor, operation_name, *args, **kwargs)

    with ExitStack() as stack:

        def lose_access():
            if loss == "membership":
                WorkspaceUser.objects.filter(user=user, workspace=workspace).delete()
            else:
                # Still a member, but with a role that can't export anymore.
                stack.enter_context(
                    patch.object(CoreHandler, "check_permissions", deny_export)
                )

        with change_before_the_job_runs(lose_access):
            job = update_content(user, root, workspace, [database])

    assert job.state == JOB_FAILED
    assert job.error_code == "PermissionException"
    assert revisions_of(root) == []
    assert_no_job_content_left(job)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_content_fails_when_its_source_is_gone_before_it_runs(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    def delete_the_source():
        Workspace.objects.filter(id=workspace.id).delete()

    # It doesn't fall back to copying the content of the latest revision, as if
    # only the details changed.
    with change_before_the_job_runs(delete_the_source):
        job = update_content(user, root, workspace, [database])

    assert job.state == JOB_FAILED
    assert job.error_code == "WorkspaceDoesNotExist"
    assert revisions_of(root) == []
    assert_no_job_content_left(job)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
def test_update_user_template_fails_when_its_category_is_deleted_during_the_update(
    data_fixture, use_tmp_media_root, mode
):
    user = data_fixture.create_user()
    category = TemplateCategory.objects.create(name="Going away")
    root = create_template(data_fixture, user)
    root.categories.set([category])
    kwargs = {"category_ids": [category.id]} if mode == "details" else {}

    job = update_while_changing(
        data_fixture, user, root, mode, category.delete, **kwargs
    )

    assert job.state == JOB_FAILED
    assert job.error_code == "InvalidTemplateCategory"
    assert job.revision_id is None
    assert revisions_of(root) == []
    assert_no_job_content_left(job)
    assert Workspace.objects.filter(id=root.workspace_id).exists()


def remove_content(root, removal):
    if removal == "workspace":
        Template.objects.filter(id=root.id).update(workspace=None)
    else:
        Template.objects.filter(id=root.id).update(pruned_at=django_timezone.now())


@pytest.mark.django_db
@pytest.mark.parametrize("removal", ["workspace", "pruned"])
def test_update_user_template_details_without_content(data_fixture, removal):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    remove_content(root, removal)

    # Refused before the job is created.
    with pytest.raises(TemplateHasNoContent):
        update_details(user, root)

    assert not CreateUserTemplateJob.objects.exists()
    assert revisions_of(root) == []


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("removal", ["workspace", "pruned"])
def test_update_user_template_details_fails_when_content_is_removed_before_it_runs(
    data_fixture, use_tmp_media_root, removal
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspaces_before = set(Workspace.objects_and_trash.values_list("id", flat=True))

    with change_before_the_job_runs(lambda: remove_content(root, removal)):
        job = update_details(user, root)

    assert job.state == JOB_FAILED
    assert job.error_code == "TemplateHasNoContent"
    assert job.human_readable_error
    assert job.revision_id is None
    assert revisions_of(root) == []
    assert (
        set(Workspace.objects_and_trash.values_list("id", flat=True))
        == workspaces_before
    )


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
def test_update_user_template_fails_when_changed_during_the_update(
    data_fixture, use_tmp_media_root, mode
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)

    def commit_another_revision():
        data_fixture.create_user_template_revision(root, icon=ICON)

    job = update_while_changing(data_fixture, user, root, mode, commit_another_revision)

    assert job.state == JOB_FAILED
    assert job.error_code == "TemplateChangedDuringUpdate"
    assert job.revision_id is None
    assert revisions_of(root) == [2]
    assert_no_job_content_left(job)
    assert Workspace.objects.filter(id=root.workspace_id).exists()


@pytest.mark.django_db
def test_update_user_template_without_base_revision_counts_as_changed(
    data_fixture,
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)

    with pytest.raises(TemplateChangedDuringUpdate):
        UpdateUserTemplateActionType.do(
            user,
            root,
            None,
            None,
            [],
            name="x",
            description="",
            icon=ICON,
            category_ids=[],
        )

    assert revisions_of(root) == []


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
@pytest.mark.parametrize("change", ["mark", "delete", "transfer"])
def test_update_user_template_fails_when_the_template_is_lost_during_the_update(
    data_fixture, use_tmp_media_root, mode, change
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    root_workspace_id = root.workspace_id

    def lose_the_template():
        templates = Template.objects.filter(id=root.id)
        if change == "mark":
            templates.update(marked_for_deletion_at=django_timezone.now())
        elif change == "delete":
            templates.get().delete()
        else:
            templates.update(owner=data_fixture.create_user())

    job = update_while_changing(data_fixture, user, root, mode, lose_the_template)

    assert job.state == JOB_FAILED
    assert job.error_code == "TemplateDoesNotExist"
    assert job.revision_id is None
    assert not Template.objects.filter(root_id=root.id).exists()
    assert_no_job_content_left(job)
    if change != "delete":
        assert Workspace.objects.filter(id=root_workspace_id).exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_cancelled_right_before_the_commit(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    save_template = CreateUserTemplateJobType._save_template

    def cancel_before_saving(self, job, revision):
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        save_template(self, job, revision)

    with patch.object(
        CreateUserTemplateJobType, "_save_template", cancel_before_saving
    ):
        job = update_details(user, root)

    assert job.state == JOB_CANCELLED
    assert job.template_id == root.id
    assert job.revision_id is None
    assert revisions_of(root) == []
    # The shared content of the root isn't the job's to delete.
    assert job.template_workspace_id is None
    assert Workspace.objects.filter(id=root.workspace_id).exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_cannot_be_cancelled_after_the_commit(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    do = UpdateUserTemplateActionType.do

    def cancel_after_creating(action_type, *args, **kwargs):
        revision = do(*args, **kwargs)
        with pytest.raises(JobNotCancellable):
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return revision

    with patch.object(UpdateUserTemplateActionType, "do", cancel_after_creating):
        job = update_details(user, root)

    assert job.state == JOB_FINISHED
    assert Template.objects.get(root=root).id == job.revision_id


@pytest.mark.django_db
def test_update_user_template_job_can_be_cancelled_until_the_commit(data_fixture):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    job = CreateUserTemplateJob(user=user, template=root, base_revision=root)

    assert CreateUserTemplateJobType().is_cancellable(job)
    job.revision = data_fixture.create_user_template_revision(root, icon=ICON)
    assert not CreateUserTemplateJobType().is_cancellable(job)


@pytest.mark.django_db(transaction=True)
def test_sweep_cleans_up_uncommitted_update_jobs_only(data_fixture, use_tmp_media_root):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    storage = get_default_storage()

    def create_failed_update_job(**kwargs):
        workspace = data_fixture.create_workspace(name="Copy")
        archive_name = storage.save(
            "template-revisions/update.zip", ContentFile(b"archive")
        )
        return CreateUserTemplateJob.objects.create(
            user=user,
            state=JOB_FAILED,
            template=root,
            base_revision=root,
            name="Copy",
            icon=ICON,
            template_workspace=workspace,
            archive_name=archive_name,
            **kwargs,
        )

    uncommitted = create_failed_update_job()
    committed = create_failed_update_job()
    revision = data_fixture.create_user_template_revision(
        root,
        icon=ICON,
        workspace=committed.template_workspace,
        archive=committed.archive_name,
    )
    committed.revision = revision
    committed.save()

    delete_orphaned_user_template_workspaces()

    assert not Workspace.objects_and_trash.filter(
        id=uncommitted.template_workspace_id
    ).exists()
    assert not storage.exists(uncommitted.archive_name)
    assert Workspace.objects.filter(id=committed.template_workspace_id).exists()
    assert storage.exists(committed.archive_name)
    assert Template.objects.filter(id=root.id).exists()


@pytest.mark.django_db(transaction=True)
def test_deleting_an_update_job_deletes_its_uncommitted_content_only(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    storage = get_default_storage()

    def create_update_job():
        workspace = data_fixture.create_workspace(name="Copy")
        archive_name = storage.save(
            "template-revisions/update.zip", ContentFile(b"archive")
        )
        return CreateUserTemplateJob.objects.create(
            user=user,
            template=root,
            base_revision=root,
            name="Copy",
            icon=ICON,
            template_workspace=workspace,
            archive_name=archive_name,
        )

    uncommitted = create_update_job()
    committed = create_update_job()
    committed.revision = data_fixture.create_user_template_revision(
        root,
        icon=ICON,
        workspace=committed.template_workspace,
        archive=committed.archive_name,
    )
    committed.save()

    JobHandler().delete_job(uncommitted)
    JobHandler().delete_job(committed)

    assert not Workspace.objects_and_trash.filter(
        id=uncommitted.template_workspace_id
    ).exists()
    assert not storage.exists(uncommitted.archive_name)
    # The committed content is the revision's.
    assert Workspace.objects.filter(id=committed.template_workspace_id).exists()
    assert storage.exists(committed.archive_name)


def delete_the_template(user, root):
    with transaction.atomic():
        UserTemplateService().delete_template(user, root.id)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
def test_update_user_template_queued_before_the_template_is_deleted(
    data_fixture, use_tmp_media_root, mode
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    template_ids = set(Template.objects.values_list("id", flat=True))
    workspace_ids = set(Workspace.objects_and_trash.values_list("id", flat=True))

    # The job waits for a worker: the task isn't run yet.
    with patch("baserow.core.jobs.handler.run_async_job") as queued:
        if mode == "details":
            job = update_details(user, root)
        else:
            job = update_content(user, root, workspace, [database])
    queued.assert_called_once_with(job.id)
    assert job.state == JOB_PENDING

    delete_the_template(user, root)
    run_async_job(job.id)

    job = CreateUserTemplateJob.objects.get(id=job.id)
    assert job.state == JOB_CANCELLED
    assert job.revision_id is None
    assert job.template_id == root.id
    # Nothing is created: no revision, and no new template as if it were a create.
    assert set(Template.objects.values_list("id", flat=True)) == template_ids
    assert set(Workspace.objects_and_trash.values_list("id", flat=True)) == (
        workspace_ids
    )
    assert_no_job_content_left(job)
    assert Template.objects.get(id=root.id).marked_for_deletion_at is not None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_runs_when_the_deletion_of_its_template_rolls_back(
    data_fixture, use_tmp_media_root
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)

    with patch("baserow.core.jobs.handler.run_async_job") as queued:
        job = update_details(user, root)
    queued.assert_called_once_with(job.id)

    # The deletion cancels the job, then fails when it's registered.
    with (
        patch.object(
            DeleteUserTemplateActionType, "register_action", side_effect=RuntimeError
        ),
        pytest.raises(RuntimeError),
    ):
        action_type_registry.get_by_type(DeleteUserTemplateActionType).do(user, root.id)
    assert Template.objects.get(id=root.id).marked_for_deletion_at is None

    run_async_job(job.id)

    job = CreateUserTemplateJob.objects.get(id=job.id)
    assert job.state == JOB_FINISHED, job.error
    assert revisions_of(root) == [2]


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
def test_update_user_template_running_when_the_template_is_deleted(
    data_fixture, use_tmp_media_root, mode
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    template_ids = set(Template.objects.values_list("id", flat=True))
    cancel_job = JobHandler.cancel_job

    with patch.object(
        JobHandler, "cancel_job", side_effect=cancel_job
    ) as cancel_job_spy:
        job = update_while_changing(
            data_fixture, user, root, mode, lambda: delete_the_template(user, root)
        )

    job = CreateUserTemplateJob.objects.get(id=job.id)
    # The delete cancels the running job in both modes.
    cancel_job_spy.assert_called_once()
    assert cancel_job_spy.call_args.args[0].id == job.id
    if mode == "details":
        # The next progress update notices the cancel.
        assert job.state == JOB_CANCELLED, job.error
    else:
        # The commit refuses the marked template before any cancel check, and the
        # job runner saves that failure over the accepted cancel (U-003).
        assert job.state == JOB_FAILED
        assert job.error_code == "TemplateDoesNotExist"
        assert job.error == f"The template {root.id} does not exist."
    assert job.revision_id is None
    assert set(Template.objects.values_list("id", flat=True)) == template_ids
    assert_no_job_content_left(job)
    assert Template.objects.get(id=root.id).marked_for_deletion_at is not None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode", ["details", "content"])
def test_update_user_template_task_running_after_the_template_is_removed(
    data_fixture, use_tmp_media_root, mode
):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    with patch("baserow.core.jobs.handler.run_async_job") as queued:
        if mode == "details":
            job = update_details(user, root)
        else:
            job = update_content(user, root, workspace, [database])
    queued.assert_called_once_with(job.id)

    delete_the_template(user, root)
    Template.objects.filter(id=root.id).update(
        marked_for_deletion_at=django_timezone.now()
        - USER_TEMPLATE_DELETION_GRACE_PERIOD
        - timedelta(hours=1)
    )
    delete_orphaned_user_template_workspaces()

    assert not Template.objects.filter(id=root.id).exists()
    assert not Job.objects.filter(id=job.id).exists()
    template_count = Template.objects.count()
    workspace_ids = set(Workspace.objects_and_trash.values_list("id", flat=True))

    # The task of the job, picked up by a worker after the purge.
    with pytest.raises(Job.DoesNotExist):
        run_async_job(job.id)

    # Nothing is created, no new template as if it were a create.
    assert Template.objects.count() == template_count
    assert set(Workspace.objects_and_trash.values_list("id", flat=True)) == (
        workspace_ids
    )
