from unittest.mock import patch

import pytest

from baserow.core.actions import InstallTemplateActionType
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import InstallTemplateJob, Template
from baserow_enterprise.audit_log.models import AuditLogEntry

install_test = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def install_marks(test):
    for mark in reversed(install_test):
        test = mark(test)
    return test


def create_template(enterprise_data_fixture, user):
    root = enterprise_data_fixture.create_user_template(user=user)
    # A revision, so that the logged id is the one of the family, not the revision.
    revision = enterprise_data_fixture.create_user_template_revision(root)
    for name in ["First", "Second"]:
        enterprise_data_fixture.create_database_application(
            workspace=revision.workspace, name=name
        )
    return root


def install(user, workspace, root):
    job = JobHandler().create_and_start_job(
        user,
        InstallTemplateJobType.type,
        sync=True,
        workspace_id=workspace.id,
        template_id=root.id,
    )
    return InstallTemplateJob.objects.get(id=job.id)


def install_entries():
    return AuditLogEntry.objects.filter(action_type=InstallTemplateActionType.type)


@install_marks
def test_install_user_template_job_is_audit_logged(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    root = create_template(enterprise_data_fixture, user)

    job = install(user, workspace, root)

    assert job.state == JOB_FINISHED
    assert job.template_id != root.id
    entry = install_entries().get()
    assert entry.workspace_id == workspace.id
    assert entry.actor_id == user.id
    assert entry.action_params["template_id"] == root.id
    assert entry.action_params["template_name"] == job.template.name
    assert entry.action_params["installed_application_ids"] == (
        job.installed_applications
    )


@install_marks
def test_failed_install_user_template_is_not_audit_logged(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    root = create_template(enterprise_data_fixture, user)
    import_application = ImportExportHandler.import_application
    calls = []

    def import_application_raising(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("Import failed")
        return import_application(self, *args, **kwargs)

    with (
        patch.object(
            ImportExportHandler, "import_application", import_application_raising
        ),
        pytest.raises(RuntimeError),
    ):
        install(user, workspace, root)

    assert InstallTemplateJob.objects.get().state == JOB_FAILED
    assert not install_entries().exists()


@install_marks
def test_install_user_template_cancelled_before_commit_is_not_audit_logged(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    root = create_template(enterprise_data_fixture, user)
    commit_install = InstallTemplateJobType._commit_install

    def cancel_then_commit(self, job, applications):
        JobHandler.cancel_job(InstallTemplateJob.objects.get(id=job.id))
        commit_install(self, job, applications)

    with patch.object(InstallTemplateJobType, "_commit_install", cancel_then_commit):
        job = install(user, workspace, root)

    assert job.state == JOB_CANCELLED
    assert not install_entries().exists()
    assert Template.objects.get(id=root.id).install_count == 0
