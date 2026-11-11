import pytest

from baserow.core.actions import InstallTemplateActionType
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.models import InstallTemplateJob
from baserow_enterprise.audit_log.models import AuditLogEntry
from tests.baserow.core.user_templates.utils import (
    fail_on_import,
    install,
    install_test,
)

pytestmark = install_test


def create_template(enterprise_data_fixture, user):
    root = enterprise_data_fixture.create_user_template(user=user)
    # A revision, so that the logged id is the one of the family, not the revision.
    revision = enterprise_data_fixture.create_user_template_revision(root)
    for name in ["First", "Second"]:
        enterprise_data_fixture.create_database_application(
            workspace=revision.workspace, name=name
        )
    return root


def install_entries():
    return AuditLogEntry.objects.filter(action_type=InstallTemplateActionType.type)


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


def test_failed_install_user_template_is_not_audit_logged(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    root = create_template(enterprise_data_fixture, user)

    with fail_on_import(RuntimeError("Import failed")), pytest.raises(RuntimeError):
        install(user, workspace, root)

    assert InstallTemplateJob.objects.get().state == JOB_FAILED
    assert not install_entries().exists()
