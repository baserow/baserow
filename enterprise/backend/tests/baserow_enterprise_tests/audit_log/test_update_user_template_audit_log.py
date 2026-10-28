from unittest.mock import patch

import pytest

from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Template
from baserow.core.user_templates.actions import UpdateUserTemplateActionType
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow.core.user_templates.models import CreateUserTemplateJob
from baserow_enterprise.audit_log.models import AuditLogEntry
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_template,
    update_content,
    update_details,
)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_content_is_audit_logged_in_the_source_workspace(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    template = create_template(enterprise_data_fixture, user, name="Mine")
    database = enterprise_data_fixture.create_database_application(user=user)

    job = update_content(user, template, database.workspace, [database])

    assert job.state == JOB_FINISHED, job.error
    entry = AuditLogEntry.objects.get(action_type=UpdateUserTemplateActionType.type)
    assert entry.workspace_id == database.workspace_id
    assert entry.action_params == {
        "template_id": template.id,
        "template_name": "Mine",
        "revision_id": job.revision_id,
        "version": 2,
        "workspace_id": database.workspace_id,
        "workspace_name": database.workspace.name,
        "application_ids": [database.id],
    }
    assert entry.type == "Update template"
    assert entry.description == f'Template "Mine" ({template.id}) updated'


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_details_is_audit_logged_without_a_workspace(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    template = create_template(enterprise_data_fixture, user, name="Mine")

    job = update_details(user, template, name="Renamed", description="", icon=ICON)

    assert job.state == JOB_FINISHED, job.error
    entry = AuditLogEntry.objects.get(action_type=UpdateUserTemplateActionType.type)
    assert entry.workspace_id is None
    assert entry.action_params["revision_id"] == job.revision_id
    assert entry.action_params["workspace_id"] is None
    assert entry.description == f'Template "Renamed" ({template.id}) updated'


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_update_user_template_cancelled_at_the_end_is_not_audit_logged(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    template = create_template(enterprise_data_fixture, user, name="Mine")
    save_template = CreateUserTemplateJobType._save_template

    def cancel_before_saving(self, job, revision):
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        save_template(self, job, revision)

    with patch.object(
        CreateUserTemplateJobType, "_save_template", cancel_before_saving
    ):
        job = update_details(user, template, name="Renamed", description="", icon=ICON)

    assert job.state == JOB_CANCELLED
    assert not Template.objects.filter(root=template).exists()
    assert not AuditLogEntry.objects.filter(
        action_type=UpdateUserTemplateActionType.type
    ).exists()
