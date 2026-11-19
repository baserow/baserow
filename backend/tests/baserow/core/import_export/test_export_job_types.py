import threading
from contextlib import contextmanager

from django.db import connection, transaction
from django.urls import reverse

import pytest
from rest_framework.test import APIClient

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs import handler as jobs_handler
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import ExportApplicationsJob
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import (
    permanently_delete_workspace,
    wait_for_a_lock_waiter,
)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_no_exported_files_on_error(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_database_application(workspace=workspace)

    with pytest.raises(UserNotInWorkspace):
        job = JobHandler().create_and_start_job(
            user,
            ExportApplicationsJobType.type,
            workspace_id=workspace.id,
            application_ids=[],
            sync=True,
        )
        assert job.state == JOB_FAILED
        assert job.resource is None

    assert ExportApplicationsJob.objects.count() == 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_success_export(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    job = JobHandler().create_and_start_job(
        user,
        ExportApplicationsJobType.type,
        workspace_id=workspace.id,
        application_ids=[],
        sync=True,
    )
    assert job.state == JOB_FINISHED
    assert job.resource is not None


def start_export(user, workspace):
    return JobHandler().create_and_start_job(
        user,
        ExportApplicationsJobType.type,
        workspace_id=workspace.id,
        application_ids=[],
        sync=True,
    )


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "when,trashed_only",
    [
        ("before_the_start", False),
        ("during_the_work", False),
        ("after_the_work", False),
        ("while_the_job_ends", False),
        ("after_the_work", True),
    ],
)
def test_export_job_fails_when_workspace_deleted(
    data_fixture, monkeypatch, test_thread, use_tmp_media_root, when, trashed_only
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)
    _, admin_token = data_fixture.create_user_and_token(is_staff=True)

    def remove_workspace():
        if trashed_only:
            with transaction.atomic():
                TrashHandler.trash(user, workspace, None, workspace)
        else:
            permanently_delete_workspace(workspace)

    workspace_locked = threading.Event()
    permanently_delete = TrashHandler.permanently_delete

    def delete_once_the_job_waits(*args):
        workspace_locked.set()
        wait_for_a_lock_waiter()
        permanently_delete(*args)

    def delete_in_another_connection():
        try:
            APIClient().delete(
                reverse("api:admin:workspaces:edit", args=[workspace.id]),
                HTTP_AUTHORIZATION=f"JWT {admin_token}",
            )
        finally:
            connection.close()

    job_type = job_type_registry.get(ExportApplicationsJobType.type)
    if when == "before_the_start":

        def remove_then_run(job_id):
            remove_workspace()
            run_async_job(job_id)

        monkeypatch.setattr(jobs_handler, "run_async_job", remove_then_run)
    elif when == "during_the_work":
        export = ImportExportHandler.export_multiple_applications

        def remove_then_export(self, applications, *args, **kwargs):
            applications = list(applications)
            remove_workspace()
            return export(self, applications, *args, **kwargs)

        monkeypatch.setattr(
            ImportExportHandler, "export_multiple_applications", remove_then_export
        )
    else:
        run_without_transaction = job_type.transaction_atomic_context

        @contextmanager
        def remove_when_the_work_ends(job):
            with run_without_transaction(job):
                yield
            if when == "after_the_work":
                remove_workspace()
            else:
                monkeypatch.setattr(
                    TrashHandler, "permanently_delete", delete_once_the_job_waits
                )
                thread.start()
                assert workspace_locked.wait(10)

        monkeypatch.setattr(
            job_type, "transaction_atomic_context", remove_when_the_work_ends
        )

    with test_thread(delete_in_another_connection) as thread:
        start_export(user, workspace)

    job = ExportApplicationsJob.objects.get(user=user)
    if trashed_only:
        assert job.state == JOB_FINISHED
        assert job.workspace_id == workspace.id
        assert job.resource is not None
    else:
        assert job.state == JOB_FAILED
        assert job.human_readable_error == "The requested workspace does not exist."
        assert job.error_code == "WorkspaceDoesNotExist"
        assert job.workspace_id is None
    if when == "during_the_work":
        monkeypatch.undo()
        other_workspace = data_fixture.create_workspace(user=user)
        assert start_export(user, other_workspace).state == JOB_FINISHED
