from unittest.mock import patch

import pytest

from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FINISHED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Template
from baserow.core.user_templates.actions import CreateUserTemplateActionType
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import CreateUserTemplateJob
from baserow_enterprise.audit_log.models import AuditLogEntry
from tests.baserow.core.user_templates.utils import start_job


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_create_user_template_job_is_audit_logged(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    job = start_job(user, database.workspace, [database])

    assert job.state == JOB_FINISHED
    entry = AuditLogEntry.objects.get(action_type=CreateUserTemplateActionType.type)
    assert entry.action_params["template_id"] == job.template_id


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_create_user_template_job_cancelled_at_the_end_is_not_audit_logged(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    create_template_root = UserTemplateHandler.create_template_root

    def cancel_after_creating(self, **kwargs):
        template = create_template_root(self, **kwargs)
        JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return template

    with patch.object(
        UserTemplateHandler, "create_template_root", cancel_after_creating
    ):
        job = start_job(user, database.workspace, [database])

    assert job.state == JOB_CANCELLED
    assert not Template.objects.exists()
    assert not AuditLogEntry.objects.filter(
        action_type=CreateUserTemplateActionType.type
    ).exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_create_user_template_job_refused_cancel_keeps_the_audit_log_entry(
    enterprise_data_fixture, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    do = CreateUserTemplateActionType.do

    def cancel_after_creating(action_type, *args, **kwargs):
        template = do(*args, **kwargs)
        with pytest.raises(JobNotCancellable):
            JobHandler.cancel_job(CreateUserTemplateJob.objects.get())
        return template

    with patch.object(CreateUserTemplateActionType, "do", cancel_after_creating):
        job = start_job(user, database.workspace, [database])

    assert job.state == JOB_FINISHED
    entry = AuditLogEntry.objects.get(action_type=CreateUserTemplateActionType.type)
    assert entry.action_params["template_id"] == Template.objects.get().id
