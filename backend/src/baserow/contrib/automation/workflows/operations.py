from abc import ABC

from baserow.contrib.automation.operations import AutomationOperationType


class AutomationWorkflowOperationType(AutomationOperationType, ABC):
    context_scope_name = "automation_workflow"


class CreateWorkflowOperationType(AutomationOperationType):
    type = "automation.workflow.create"


class DeleteWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.delete"


class UpdateWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.update"


class ReadWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.read"


class DuplicateWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.duplicate"
