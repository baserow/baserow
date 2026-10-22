import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import connection, transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import ChoiceElement
from baserow.contrib.database.views.models import View
from baserow.contrib.integrations.core.models import SMTPIntegration
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowFieldsUpdated,
    LocalBaserowIntegration,
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
)
from baserow.core.cache import local_cache
from baserow.core.exceptions import (
    PermissionDenied,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs.constants import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_FINISHED,
    JOB_STARTED,
)
from baserow.core.jobs.exceptions import (
    JobCancelled,
    JobNotCancellable,
    MaxJobCountExceeded,
)
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import (
    Application,
    ImportExportResource,
    Template,
    Workspace,
    WorkspaceUser,
)
from baserow.core.operations import ExportWorkspaceOperationType
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.actions import CreateUserTemplateActionType
from baserow.core.user_templates.constants import USER_TEMPLATE_DELETION_GRACE_PERIOD
from baserow.core.user_templates.exceptions import NoApplicationsSelected
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow.core.user_templates.models import (
    CreateUserTemplateJob,
    UserTemplateContentToDelete,
)
from baserow.core.user_templates.service import UserTemplateService
from baserow.core.user_templates.tasks import delete_orphaned_user_template_workspaces
from baserow.core.utils import Progress
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

pytestmark = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def assert_no_content_left(workspace_ids, archive_name=""):
    assert Template.objects.count() == 0
    assert not Workspace.objects_and_trash.filter(id__in=workspace_ids).exists()
    if archive_name:
        assert not get_default_storage().exists(archive_name)


def assert_no_copy_left(source_workspace):
    assert Template.objects.count() == 0
    assert list(Workspace.objects_and_trash.all()) == [source_workspace]
    storage = get_default_storage()
    if storage.exists("template-revisions"):
        assert storage.listdir("template-revisions")[1] == []


def test_create_user_template_job(data_fixture):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]
    category = data_fixture.create_template_category()
    applications = [
        source["database"],
        source["builder"],
        source["dashboard"],
        source["automation"],
    ]

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        job = start_job(
            user, workspace, applications, category_ids=[category.id], name="Mine"
        )

    assert job.state == JOB_FINISHED
    template = Template.objects.get()
    job.refresh_from_db()
    assert job.template == template
    assert template.owner == user
    assert template.name == "Mine"
    assert template.description == "What it does"
    assert template.icon == ICON
    assert list(template.categories.all()) == [category]
    assert template.type == Template.Type.USER
    assert template.review_state == Template.ReviewState.NOT_SUBMITTED
    assert template.archive.name == job.archive_name
    template.full_clean(exclude=["open_application"])

    template_workspace = template.workspace
    assert template_workspace.name == "Mine"
    assert job.template_workspace == template_workspace
    assert not WorkspaceUser.objects.filter(workspace=template_workspace).exists()
    assert set(copied_applications(template)) == {
        "database",
        "builder",
        "dashboard",
        "automation",
    }
    assert get_default_storage().exists(job.archive_name)
    assert set(
        Application.objects.filter(workspace=workspace).values_list("id", flat=True)
    ) == {application.id for application in applications}

    assert ImportExportResource.objects.count() == 0
    assert ImportExportResource.objects_and_trash.count() == 2
    ImportExportHandler().permanently_delete_trashed_resources()
    assert ImportExportResource.objects_and_trash.count() == 0
    assert get_default_storage().exists(job.archive_name)

    action_done.assert_called_once()
    action_kwargs = action_done.call_args.kwargs
    assert action_kwargs["action_type"].type == "create_user_template"
    assert action_kwargs["workspace"] == workspace
    assert action_kwargs["action_params"] == {
        "template_id": template.id,
        "template_name": "Mine",
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "application_ids": [application.id for application in applications],
    }


def test_create_user_template_job_content_rules(data_fixture):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]

    job = start_job(
        user,
        workspace,
        [source["database"], source["builder"], source["dashboard"]],
    )

    template_workspace = job.template.workspace
    assert not WorkspaceUser.objects.filter(workspace=template_workspace).exists()
    applications = copied_applications(job.template)
    table = applications["database"].table_set.get()
    assert list(View.objects.filter(table=table).values_list("name", flat=True)) == [
        "Shared"
    ]
    collaborators_field = next(
        field.specific
        for field in table.field_set.all()
        if field.specific_class.__name__ == "MultipleCollaboratorsField"
    )
    row = table.get_model().objects.get()
    assert getattr(row, collaborators_field.db_column).count() == 0

    integrations = LocalBaserowIntegration.objects.filter(
        application__in=[applications["builder"], applications["dashboard"]]
    )
    assert len(integrations) == 2
    assert all(
        integration.authorized_subject_id is None for integration in integrations
    )
    data_sources = {
        data_source.name: data_source.service.specific
        for data_source in DataSource.objects.filter(
            page__builder=applications["builder"]
        )
    }
    # The database was copied along, so the builder points at the copy.
    assert data_sources["List"].table_id == table.id
    assert data_sources["Aggregate"].table_id == table.id
    text_field = table.field_set.get(primary=True)
    assert data_sources["Aggregate"].field_id == text_field.id
    dashboard_service = LocalBaserowAggregateRows.objects.get(
        dashboard_data_source__dashboard=applications["dashboard"]
    )
    assert dashboard_service.field_id == text_field.id


def test_create_user_template_job_strips_automation_secrets(data_fixture):
    source = create_source(data_fixture)

    job = start_job(source["user"], source["workspace"], [source["automation"]])

    applications = copied_applications(job.template)
    smtp = SMTPIntegration.objects.get(application=applications["automation"])
    assert not smtp.password
    assert not smtp.username
    assert not smtp.host


def test_create_user_template_job_clears_references_outside_the_selection(data_fixture):
    source = create_source(data_fixture)

    job = start_job(
        source["user"],
        source["workspace"],
        [source["builder"], source["dashboard"], source["automation"]],
    )

    applications = copied_applications(job.template)
    assert set(applications) == {"builder", "dashboard", "automation"}
    services = [
        data_source.service.specific
        for data_source in DataSource.objects.filter(
            page__builder=applications["builder"]
        )
    ] + list(
        LocalBaserowAggregateRows.objects.filter(
            dashboard_data_source__dashboard=applications["dashboard"]
        )
    )
    assert len(services) == 3
    for service in services:
        assert service.table_id is None
        assert service.view_id is None
        assert getattr(service, "field_id", None) is None
        assert not LocalBaserowTableServiceFilter.objects.filter(service=service)
        assert not LocalBaserowTableServiceSort.objects.filter(service=service)
    trigger = LocalBaserowFieldsUpdated.objects.get(
        automation_workflow_node__workflow__automation=applications["automation"]
    )
    assert trigger.table_id is None
    assert trigger.field_ids == []
    # A formula keeps a reference it can't map, which resolves to nothing.
    choice = ChoiceElement.objects.get(page__builder=applications["builder"])
    assert choice.formula_value["formula"].endswith(
        f".{source['text_field'].db_column}.*.value')"
    )

    archive = read_archive(job.archive_name)
    assert archive
    for key, value in find_values(archive, CLEARED_KEYS):
        assert value in (None, ""), f"{key} = {value}"


def test_create_user_template_job_without_export_permission(data_fixture):
    source = create_source(data_fixture)
    check_permissions = CoreHandler.check_permissions

    def deny_export(self, actor, operation_name, *args, **kwargs):
        if operation_name == ExportWorkspaceOperationType.type:
            raise PermissionDenied()
        return check_permissions(self, actor, operation_name, *args, **kwargs)

    with patch.object(CoreHandler, "check_permissions", deny_export):
        with pytest.raises(PermissionDenied):
            start_job(source["user"], source["workspace"], [source["builder"]])

    assert CreateUserTemplateJob.objects.count() == 0
    assert Template.objects.count() == 0


def test_create_user_template_job_refuses_foreign_and_trashed_applications(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    foreign = data_fixture.create_database_application(workspace=other_workspace)
    trashed = data_fixture.create_database_application(
        workspace=workspace, trashed=True
    )

    with pytest.raises(PermissionDenied):
        start_job(user, workspace, [database, foreign])
    with pytest.raises(PermissionDenied):
        start_job(user, workspace, [database, trashed])
    with pytest.raises(NoApplicationsSelected):
        start_job(user, workspace, [])
    with pytest.raises(UserNotInWorkspace):
        start_job(data_fixture.create_user(), workspace, [database])

    assert CreateUserTemplateJob.objects.count() == 0
    assert Template.objects.count() == 0


@pytest.mark.django_db
def test_get_exportable_applications_refuses_a_trashed_workspace(data_fixture):
    # The workspace can be trashed while the job waits for a worker. Its members
    # are refused before its applications are filtered, like for an export.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    workspace.trashed = True
    workspace.save()

    with pytest.raises(UserNotInWorkspace):
        UserTemplateService().get_exportable_applications(
            user, workspace, [database.id]
        )


def test_create_user_template_job_refuses_a_template_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_template(workspace=workspace)

    with pytest.raises(PermissionDenied):
        start_job(user, workspace, [database])


def test_create_user_template_job_fails_when_access_is_lost_before_it_runs(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    get_exportable_applications = UserTemplateService.get_exportable_applications
    calls = []

    def lose_access_on_run(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            WorkspaceUser.objects.filter(user=user, workspace=workspace).delete()
            # The job runs in its own worker, without what this test has cached.
            local_cache.clear()
        return get_exportable_applications(self, *args, **kwargs)

    with patch.object(
        UserTemplateService, "get_exportable_applications", lose_access_on_run
    ):
        job = start_job(user, workspace, [database])

    assert job.state == JOB_FAILED
    assert job.error_code == "PermissionException"
    assert_no_copy_left(workspace)


@pytest.mark.django_db
def test_create_user_template_job_fails_when_the_source_workspace_is_gone(
    data_fixture,
):
    user = data_fixture.create_user()
    job = create_unfinished_job(data_fixture, user, state=JOB_STARTED)
    job.source_workspace = None

    with pytest.raises(WorkspaceDoesNotExist):
        CreateUserTemplateJobType().run(job, Progress(100))


def test_create_user_template_job_cleans_up_on_error(data_fixture):
    source = create_source(data_fixture)

    with patch(
        "baserow.core.import_export.handler.ImportExportHandler."
        "import_multiple_applications",
        side_effect=PermissionDenied("Fails mid-import"),
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_FAILED
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cleans_up_on_error_after_storing_the_archive(
    data_fixture,
):
    source = create_source(data_fixture)

    with patch(
        "baserow.core.user_templates.handler.UserTemplateHandler.create_template_root",
        side_effect=PermissionDenied("Fails at the end"),
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_FAILED
    assert job.archive_name
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cleans_up_an_archive_written_before_an_error(
    data_fixture,
):
    source = create_source(data_fixture)
    storage = get_default_storage()
    save = storage.save

    def save_then_fail(name, content, *args, **kwargs):
        stored_name = save(name, content, *args, **kwargs)
        if name.startswith("template-revisions/"):
            raise OSError("The connection was reset after the upload")
        return stored_name

    with patch.object(storage, "save", save_then_fail), pytest.raises(OSError):
        start_job(source["user"], source["workspace"], [source["database"]])

    assert CreateUserTemplateJob.objects.get().state == JOB_FAILED
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cleans_up_when_cancelled(data_fixture):
    source = create_source(data_fixture)
    export_workspace_applications = ImportExportHandler.export_workspace_applications
    calls = []

    def cancel_during_archive_export(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return export_workspace_applications(self, *args, **kwargs)

    with patch.object(
        ImportExportHandler,
        "export_workspace_applications",
        cancel_during_archive_export,
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert len(calls) == 2
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_raising_job_cancelled_cleans_up(data_fixture):
    source = create_source(data_fixture)

    with patch(
        "baserow.core.import_export.handler.ImportExportHandler."
        "import_multiple_applications",
        side_effect=JobCancelled(),
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cancelled_while_creating_the_template(data_fixture):
    source = create_source(data_fixture)
    create_template_root = UserTemplateHandler.create_template_root
    delete_content = UserTemplateHandler.delete_content_without_template
    templates_left_to_delete = []

    def cancel_after_creating(self, **kwargs):
        template = create_template_root(self, **kwargs)
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return template

    def record_templates(self, *args):
        templates_left_to_delete.append(Template.objects.count())
        delete_content(self, *args)

    with (
        patch.object(
            UserTemplateHandler, "create_template_root", cancel_after_creating
        ),
        patch.object(
            UserTemplateHandler, "delete_content_without_template", record_templates
        ),
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert job.template_id is None
    # Rolled back with the action, not deleted after it was committed.
    assert templates_left_to_delete == [0]
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cancelled_right_before_the_commit(data_fixture):
    source = create_source(data_fixture)
    save_template = CreateUserTemplateJobType._save_template

    def cancel_before_saving(self, job, template):
        # After the last progress report, before the job is locked.
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        save_template(self, job, template)

    with patch.object(
        CreateUserTemplateJobType, "_save_template", cancel_before_saving
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert job.template_id is None
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cancel_overwritten_in_the_cache_is_noticed(
    data_fixture,
):
    source = create_source(data_fixture)
    save_template = CreateUserTemplateJobType._save_template

    def cancel_then_report_progress(self, job, template):
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        # A progress update that read the cache before the cancel writes the
        # state of the worker back.
        job.set_cached_state()
        save_template(self, job, template)

    with patch.object(
        CreateUserTemplateJobType, "_save_template", cancel_then_report_progress
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert not Template.objects.exists()
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cancel_is_kept_when_content_is_tracked_after_it(
    data_fixture,
):
    source = create_source(data_fixture)
    track_content = CreateUserTemplateJobType._track_content

    def cancel_then_track(self, job, **content):
        if "archive_name" in content:
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
            # A progress update that read the cache before the cancel writes the
            # state of the worker back.
            job.set_cached_state()
        track_content(self, job, **content)

    with patch.object(CreateUserTemplateJobType, "_track_content", cancel_then_track):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cancel_accepted_as_it_starts_is_noticed(data_fixture):
    source = create_source(data_fixture)

    def cancel_as_the_worker_starts(user):
        # After the worker checked for a cancellation, before it saves STARTED.
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())

    with patch(
        "baserow.core.jobs.tasks.setup_user_in_sentry", cancel_as_the_worker_starts
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    job.refresh_from_db()
    assert job.state == JOB_CANCELLED
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_concurrent_cancel_waits_for_the_commit(
    data_fixture, test_thread
):
    source = create_source(data_fixture)
    save_template = CreateUserTemplateJobType._save_template
    outcome = {}

    def cancel():
        try:
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
            outcome["cancel"] = "accepted"
        except JobNotCancellable:
            outcome["cancel"] = "refused"
        finally:
            connection.close()

    with test_thread(cancel) as thread:

        def save_with_a_concurrent_cancel(self, job, template):
            save_template(self, job, template)
            thread.start()
            # The cancel waits for the lock that the job holds until it commits.
            assert not thread.thread_stopped.wait(0.3)

        with patch.object(
            CreateUserTemplateJobType, "_save_template", save_with_a_concurrent_cancel
        ):
            job = start_job(source["user"], source["workspace"], [source["database"]])

    assert outcome == {"cancel": "refused"}
    job.refresh_from_db()
    assert job.state == JOB_FINISHED
    assert Template.objects.get().id == job.template_id


def test_create_user_template_job_cleans_up_on_error_right_before_the_commit(
    data_fixture,
):
    source = create_source(data_fixture)
    save_template = CreateUserTemplateJobType._save_template

    def save_then_fail(self, job, template):
        save_template(self, job, template)
        raise RuntimeError("Fails before the commit")

    with patch.object(CreateUserTemplateJobType, "_save_template", save_then_fail):
        with pytest.raises(RuntimeError):
            start_job(source["user"], source["workspace"], [source["database"]])

    job = CreateUserTemplateJob.objects.get()
    assert job.state == JOB_FAILED
    assert job.template_id is None
    assert not Template.objects.exists()
    assert_no_copy_left(source["workspace"])


def test_create_user_template_job_cannot_be_cancelled_after_the_commit(data_fixture):
    source = create_source(data_fixture)
    do = CreateUserTemplateActionType.do

    def cancel_after_creating(action_type, *args, **kwargs):
        template = do(*args, **kwargs)
        with pytest.raises(JobNotCancellable):
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return template

    with patch.object(CreateUserTemplateActionType, "do", cancel_after_creating):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_FINISHED
    assert Template.objects.get().id == job.template_id


def test_create_user_template_job_keeps_the_template_on_error_after_the_commit(
    data_fixture,
):
    source = create_source(data_fixture)
    do = CreateUserTemplateActionType.do

    def fail_after_creating(action_type, *args, **kwargs):
        do(*args, **kwargs)
        raise PermissionDenied("Fails after the template was created")

    with patch.object(CreateUserTemplateActionType, "do", fail_after_creating):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_FAILED
    template = Template.objects.get()
    assert template.id == job.template_id
    assert template.workspace.application_set.count() == 1
    assert get_default_storage().exists(template.archive.name)


def assert_only_the_committed_template_left(job, source_workspace):
    template = Template.objects.get()
    assert job.state == JOB_FINISHED, job.error
    assert job.template_id == job.revision_id == template.id
    assert job.template_workspace_id == template.workspace_id
    assert job.archive_name == template.archive.name
    assert set(Workspace.objects_and_trash.all()) == {
        source_workspace,
        template.workspace,
    }
    assert get_default_storage().listdir("template-revisions")[1] == [
        os.path.basename(template.archive.name)
    ]


def test_create_user_template_job_redelivered_after_its_commit_isnt_run_again(
    data_fixture,
):
    source = create_source(data_fixture)
    job = start_job(source["user"], source["workspace"], [source["database"]])

    again = run_again(job.id)

    assert again.revision_id == job.revision_id
    assert_only_the_committed_template_left(again, source["workspace"])


def test_create_user_template_job_keeps_the_commit_of_another_run(data_fixture):
    source = create_source(data_fixture)

    with another_run_after_the_copy() as other_runs:
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert other_runs[0].state == JOB_FINISHED
    assert job.revision_id == other_runs[0].revision_id
    assert_only_the_committed_template_left(job, source["workspace"])


def test_create_user_template_job_failed_run_keeps_the_commit_of_another_run(
    data_fixture,
):
    source = create_source(data_fixture)

    with (
        another_run_after_the_copy(RuntimeError("Fails after the copy")) as other_runs,
        patch("baserow.core.user_templates.job_types.logger") as logger,
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.revision_id == other_runs[0].revision_id
    assert_only_the_committed_template_left(job, source["workspace"])
    logger.exception.assert_called_once()


@pytest.mark.parametrize(
    "target,error,state",
    [
        # Before this run tracked anything.
        (
            "baserow.core.user_templates.service.UserTemplateService.copy_applications",
            PermissionDenied("Fails before the copy"),
            JOB_FAILED,
        ),
        # After this run tracked its workspace.
        (
            "baserow.core.import_export.handler.ImportExportHandler."
            "import_multiple_applications",
            PermissionDenied("Fails mid-import"),
            JOB_FAILED,
        ),
        (
            "baserow.core.import_export.handler.ImportExportHandler."
            "import_multiple_applications",
            JobCancelled(),
            JOB_CANCELLED,
        ),
    ],
)
def test_create_user_template_job_keeps_the_content_another_run_tracked(
    data_fixture, target, error, state
):
    source = create_source(data_fixture)
    with patch("baserow.core.jobs.handler.run_async_job"):
        job = start_job(source["user"], source["workspace"], [source["database"]])
    # Another run of the job, still going on, tracked its copy on the row.
    other_workspace = data_fixture.create_workspace(name="Copy of the other run")
    other_archive = get_default_storage().save(
        "template-revisions/other-run.zip", ContentFile(b"archive")
    )
    CreateUserTemplateJob.objects.filter(id=job.id).update(
        template_workspace=other_workspace, archive_name=other_archive
    )

    with patch(target, side_effect=error):
        job = run_again(job.id)

    assert job.state == state
    assert set(Workspace.objects_and_trash.all()) == {
        source["workspace"],
        other_workspace,
    }
    assert get_default_storage().listdir("template-revisions")[1] == [
        os.path.basename(other_archive)
    ]


def test_create_user_template_job_logs_a_failed_clean_up_after_a_cancel(data_fixture):
    source = create_source(data_fixture)

    with (
        patch(
            "baserow.core.import_export.handler.ImportExportHandler."
            "import_multiple_applications",
            side_effect=JobCancelled(),
        ),
        patch.object(
            UserTemplateHandler,
            "delete_content_without_template",
            side_effect=RuntimeError("Storage is down"),
        ),
        patch("baserow.core.user_templates.job_types.logger") as logger,
    ):
        job = start_job(source["user"], source["workspace"], [source["database"]])

    assert job.state == JOB_CANCELLED
    logger.exception.assert_called_once()


def create_unfinished_job(data_fixture, user, **kwargs):
    template_workspace = data_fixture.create_workspace(name="Copy")
    data_fixture.create_database_application(workspace=template_workspace)
    archive_name = get_default_storage().save(
        "template-revisions/unfinished.zip", ContentFile(b"archive")
    )
    return CreateUserTemplateJob.objects.create(
        user=user,
        source_workspace=data_fixture.create_workspace(user=user),
        name="Copy",
        icon=ICON,
        template_workspace=template_workspace,
        archive_name=archive_name,
        **kwargs,
    )


def test_sweep_cleans_up_after_a_killed_worker(data_fixture, settings):
    settings.BASEROW_JOB_SOFT_TIME_LIMIT = 60
    settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT = 60
    user = data_fixture.create_user()
    now = datetime.now(tz=timezone.utc)

    with freeze_time(now - timedelta(minutes=5)):
        job = create_unfinished_job(data_fixture, user, state=JOB_STARTED)
    workspace_id, archive_name = job.template_workspace_id, job.archive_name

    with freeze_time(now):
        JobHandler().clean_up_jobs()

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert Workspace.objects.filter(id=workspace_id).exists()

    delete_orphaned_user_template_workspaces()

    job.refresh_from_db()
    assert job.template_workspace_id is None
    assert job.archive_name == ""
    assert_no_content_left([workspace_id], archive_name)
    delete_orphaned_user_template_workspaces()


def test_sweep_keeps_content_of_a_template_and_running_jobs(data_fixture):
    user = data_fixture.create_user()
    running = create_unfinished_job(data_fixture, user, state=JOB_STARTED)
    failed = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    data_fixture.create_template(workspace=failed.template_workspace)
    Template.objects.filter(workspace=failed.template_workspace).update(
        archive=failed.archive_name
    )

    delete_orphaned_user_template_workspaces()

    assert Workspace.objects.filter(id=running.template_workspace_id).exists()
    assert Workspace.objects.filter(id=failed.template_workspace_id).exists()
    assert get_default_storage().exists(running.archive_name)
    assert get_default_storage().exists(failed.archive_name)


def test_sweep_skips_a_job_that_failed_after_its_commit(data_fixture):
    user = data_fixture.create_user()
    failed = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    failed.template = data_fixture.create_template(workspace=failed.template_workspace)
    failed.revision = failed.template
    failed.save()

    with patch.object(
        UserTemplateHandler, "delete_content_without_template"
    ) as delete_content:
        delete_orphaned_user_template_workspaces()

    delete_content.assert_not_called()


def test_sweep_skips_a_job_already_cleaned_up(data_fixture):
    user = data_fixture.create_user()
    CreateUserTemplateJob.objects.create(
        user=user,
        source_workspace=data_fixture.create_workspace(user=user),
        name="Copy",
        icon=ICON,
        state=JOB_FAILED,
    )

    with patch.object(
        UserTemplateHandler, "delete_content_without_template"
    ) as delete_content:
        delete_orphaned_user_template_workspaces()

    delete_content.assert_not_called()


def test_sweep_waits_for_the_worker_of_a_cancelled_job(data_fixture, settings):
    settings.BASEROW_JOB_SOFT_TIME_LIMIT = 60
    user = data_fixture.create_user()
    now = datetime.now(tz=timezone.utc)

    with freeze_time(now - timedelta(seconds=91)):
        cancelled_long_ago = create_unfinished_job(
            data_fixture, user, state=JOB_CANCELLED
        )
    with freeze_time(now - timedelta(seconds=89)):
        cancelled_recently = create_unfinished_job(
            data_fixture, user, state=JOB_CANCELLED
        )
    workspace_id = cancelled_long_ago.template_workspace_id
    archive_name = cancelled_long_ago.archive_name

    with freeze_time(now):
        delete_orphaned_user_template_workspaces()

    assert not Workspace.objects_and_trash.filter(id=workspace_id).exists()
    assert not get_default_storage().exists(archive_name)
    # Its worker may still be running and cleans up when it notices.
    assert Workspace.objects.filter(
        id=cancelled_recently.template_workspace_id
    ).exists()
    assert get_default_storage().exists(cancelled_recently.archive_name)


def test_sweep_continues_after_a_job_fails_to_clean_up(data_fixture):
    user = data_fixture.create_user()
    broken = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    other = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    delete_content = UserTemplateHandler.delete_content_without_template

    def fail_for_broken(handler, workspace_id, archive_name):
        if workspace_id == broken.template_workspace_id:
            raise ValueError("Storage unavailable.")
        delete_content(handler, workspace_id, archive_name)

    with patch.object(
        UserTemplateHandler,
        "delete_content_without_template",
        autospec=True,
        side_effect=fail_for_broken,
    ):
        delete_orphaned_user_template_workspaces()

    broken.refresh_from_db()
    assert broken.archive_name != ""
    assert Workspace.objects.filter(id=broken.template_workspace_id).exists()
    workspace_id, archive_name = other.template_workspace_id, other.archive_name
    other.refresh_from_db()
    assert other.archive_name == ""
    assert_no_content_left([workspace_id], archive_name)


def test_deleting_an_unfinished_job_cleans_up(data_fixture):
    user = data_fixture.create_user()
    job = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    workspace_id, archive_name = job.template_workspace_id, job.archive_name

    with transaction.atomic():
        JobHandler().delete_job(job)
        # Nothing is deleted before the commit.
        assert Workspace.objects.filter(id=workspace_id).exists()

    assert_no_content_left([workspace_id], archive_name)


def test_deleting_jobs_continues_after_a_job_fails_to_clean_up(data_fixture):
    user = data_fixture.create_user()
    broken = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    other = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    workspace_id, archive_name = other.template_workspace_id, other.archive_name
    delete_content = UserTemplateHandler.delete_content_without_template

    def fail_for_broken(handler, workspace_id, archive_name):
        if workspace_id == broken.template_workspace_id:
            raise ValueError("Storage unavailable.")
        delete_content(handler, workspace_id, archive_name)

    with patch.object(
        UserTemplateHandler,
        "delete_content_without_template",
        autospec=True,
        side_effect=fail_for_broken,
    ):
        with transaction.atomic():
            JobHandler().delete_job(broken)
            JobHandler().delete_job(other)

    assert not CreateUserTemplateJob.objects.exists()
    assert Workspace.objects.filter(id=broken.template_workspace_id).exists()
    assert_no_content_left([workspace_id], archive_name)
    # The sweep retries it.
    assert list(
        UserTemplateContentToDelete.objects.values_list("workspace_id", "archive_name")
    ) == [(broken.template_workspace_id, broken.archive_name)]


def test_deleting_the_user_of_an_unfinished_job_cleans_up(data_fixture):
    user = data_fixture.create_user()
    job = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    workspace_id, archive_name = job.template_workspace_id, job.archive_name

    user.delete()

    assert not CreateUserTemplateJob.objects.exists()
    assert_no_content_left([workspace_id], archive_name)
    assert not UserTemplateContentToDelete.objects.exists()


def test_sweep_retries_the_content_of_a_deleted_job(data_fixture):
    user = data_fixture.create_user()
    job = create_unfinished_job(data_fixture, user, state=JOB_FAILED)
    workspace_id, archive_name = job.template_workspace_id, job.archive_name

    with patch.object(
        get_default_storage().__class__,
        "delete",
        side_effect=OSError("Storage unavailable."),
    ):
        user.delete()

    assert not CreateUserTemplateJob.objects.exists()
    assert get_default_storage().exists(archive_name)
    assert UserTemplateContentToDelete.objects.filter(
        archive_name=archive_name
    ).exists()

    delete_orphaned_user_template_workspaces()

    assert_no_content_left([workspace_id], archive_name)
    assert not UserTemplateContentToDelete.objects.exists()


def delete_user(user):
    type(user).objects.get(id=user.id).delete()


def test_deleting_the_user_as_the_copy_is_created_cleans_up(data_fixture):
    source = create_source(data_fixture)
    track_content = CreateUserTemplateJobType._track_content

    def delete_user_then_track(self, job, **content):
        if "template_workspace" in content:
            # The deletion of the job doesn't see the copy yet.
            delete_user(source["user"])
        track_content(self, job, **content)

    with (
        patch.object(
            CreateUserTemplateJobType, "_track_content", delete_user_then_track
        ),
        pytest.raises(Exception),
    ):
        start_job(source["user"], source["workspace"], [source["database"]])

    assert not CreateUserTemplateJob.objects.exists()
    assert_no_copy_left(source["workspace"])
    assert not UserTemplateContentToDelete.objects.exists()


def test_deleting_the_user_as_the_archive_is_stored_cleans_up(data_fixture):
    source = create_source(data_fixture)
    track_content = CreateUserTemplateJobType._track_content

    def track_then_delete_user(self, job, **content):
        track_content(self, job, **content)
        if "archive_name" in content:
            # The deletion of the job doesn't see the archive, stored after it.
            delete_user(source["user"])

    with (
        patch.object(
            CreateUserTemplateJobType, "_track_content", track_then_delete_user
        ),
        pytest.raises(Exception),
    ):
        start_job(source["user"], source["workspace"], [source["database"]])

    assert not CreateUserTemplateJob.objects.exists()
    assert_no_copy_left(source["workspace"])
    assert not UserTemplateContentToDelete.objects.exists()


def test_deleting_a_finished_job_keeps_the_template(data_fixture):
    source = create_source(data_fixture)
    job = start_job(source["user"], source["workspace"], [source["database"]])
    template = job.template

    JobHandler().delete_job(job)

    template.refresh_from_db()
    assert Workspace.objects.filter(id=template.workspace_id).exists()
    assert get_default_storage().exists(template.archive.name)


def test_create_user_template_job_max_count(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    CreateUserTemplateJob.objects.create(
        user=user, source_workspace=workspace, name="Running", icon=ICON
    )

    with pytest.raises(MaxJobCountExceeded):
        start_job(user, workspace, [database])

    export_job = JobHandler().create_and_start_job(
        user,
        ExportApplicationsJobType.type,
        workspace_id=workspace.id,
        application_ids=[],
        sync=True,
    )
    assert export_job.state == JOB_FINISHED


def test_purge_waits_for_a_create_job_that_committed_its_template(data_fixture):
    source = create_source(data_fixture)
    user, workspace = source["user"], source["workspace"]
    run = JobHandler.run
    skipped = []

    # Right after the commit the job is still running: it saves that it finished
    # after `JobHandler.run` returns.
    def run_then_purge(job):
        result = run(job)
        Template.objects.filter(id=job.template_id).update(
            marked_for_deletion_at=datetime.now(tz=timezone.utc)
            - USER_TEMPLATE_DELETION_GRACE_PERIOD
            - timedelta(hours=1)
        )
        UserTemplateHandler().delete_marked_templates()
        skipped.append(Template.objects.filter(id=job.template_id).exists())
        return result

    with patch.object(JobHandler, "run", side_effect=run_then_purge):
        job = start_job(user, workspace, [source["database"]])

    assert skipped == [True]
    job = CreateUserTemplateJob.objects.get(id=job.id)
    assert job.state == JOB_FINISHED, job.error
    template_workspace_id = job.template.workspace_id
    archive_name = job.template.archive.name

    UserTemplateHandler().delete_marked_templates()

    assert not Template.objects.filter(id=job.template_id).exists()
    assert not CreateUserTemplateJob.objects.filter(id=job.id).exists()
    assert not Workspace.objects_and_trash.filter(id=template_workspace_id).exists()
    assert not get_default_storage().exists(archive_name)
    # The workspace the template was created from is kept.
    assert Workspace.objects.filter(id=workspace.id).exists()
