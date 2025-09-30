from baserow.contrib.automation.workflows.operations import (
    DeleteAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import UserSubjectType


class AutomationWorkflowPermissionManager(PermissionManagerType):
    """Handles permissions for Automation Workflows."""

    type = "automation_workflow"
    supported_actor_types = [UserSubjectType.type]

    def check_multiple_permissions(
        self,
        checks,
        workspace=None,
        include_trash=False,
    ):
        """
        If a workflow is published, any modifications related to it
        should be disallowed.
        """

        result = {}

        for check in checks:
            if check.operation_name in [
                DeleteAutomationWorkflowOperationType.type,
                UpdateAutomationWorkflowOperationType.type,
            ]:
                if check.context.is_published:
                    result[check] = False

        return result
