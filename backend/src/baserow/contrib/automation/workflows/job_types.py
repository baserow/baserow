from typing import Any, Dict

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from rest_framework import serializers

from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.contrib.automation.api.workflows.errors import (
    ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
)
from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
)
from baserow.contrib.automation.models import DuplicateAutomationWorkflowJob
from baserow.contrib.automation.workflows.actions import (
    DuplicateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import PublishAutomationWorkflowJob
from baserow.contrib.automation.workflows.operations import (
    DuplicateAutomationWorkflowOperationType,
)
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.jobs.registries import JobType


class DuplicateAutomationWorkflowJobType(JobType):
    type = "duplicate_automation_workflow"
    model_class = DuplicateAutomationWorkflowJob
    max_count = 1

    request_serializer_field_names = ["workflow_id"]

    request_serializer_field_overrides = {
        "workflow_id": serializers.IntegerField(
            help_text="The ID of the workflow to duplicate.",
        ),
    }

    serializer_field_names = [
        "original_automation_workflow",
        "duplicated_automation_workflow",
    ]
    serializer_field_overrides = {
        "original_automation_workflow": AutomationWorkflowSerializer(read_only=True),
        "duplicated_automation_workflow": AutomationWorkflowSerializer(read_only=True),
    }

    def transaction_atomic_context(self, job: "DuplicateAutomationWorkflowJobType"):
        return transaction.atomic()

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        workflow = AutomationWorkflowHandler().get_workflow(values.pop("workflow_id"))

        CoreHandler().check_permissions(
            user,
            DuplicateAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        return {"original_automation_workflow": workflow}

    def run(self, job, progress):
        new_workflow_clone = DuplicateAutomationWorkflowActionType.do(
            job.user,
            job.original_automation_workflow,
            progress_builder=progress.create_child_builder(
                represents_progress=progress.total
            ),
        )

        job.duplicated_automation_workflow = new_workflow_clone
        job.save(update_fields=("duplicated_automation_workflow",))

        return new_workflow_clone


class PublishAutomationWorkflowJobType(JobType):
    type = "publish_automation_workflow"
    model_class = PublishAutomationWorkflowJob
    max_count = 2

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
    }

    def transaction_atomic_context(self, job: PublishAutomationWorkflowJob):
        # It's possible for the AutomationWorkflow to be deleted prior to
        # the execution of this task (e.g. the export worker queue is down,
        # and brought up again).
        if not job.automation_workflow:
            raise AutomationWorkflowDoesNotExist(
                "The AutomationWorkflow has been deleted prior to the "
                "execution of this task."
            )

        application_type = job.automation_workflow.automation.get_type()
        return application_type.export_safe_transaction_context(
            job.automation_workflow.automation
        )

    def run(self, job: PublishAutomationWorkflowJob, progress):
        from baserow.contrib.automation.workflows.service import (
            AutomationWorkflowService,
        )

        AutomationWorkflowService().publish(job.user, job.automation_workflow, progress)
