from abc import ABC

from baserow.contrib.automation.operations import AutomationOperationType


class AutomationWorkflowOperationType(AutomationOperationType, ABC):
    context_scope_name = "automation_workflow"


class CreateAutomationWorkflowOperationType(AutomationOperationType):
    type = "automation.create_workflow"


class DeleteAutomationWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.delete"


class UpdateAutomationWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.update"


class ReadAutomationWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.read"


class DuplicateAutomationWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.duplicate"


class RestoreAutomationWorkflowOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.restore"


class PublishAutomationWorkflowOperationType(AutomationOperationType):
    type = "automation.publish_workflow"
