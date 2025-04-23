from abc import ABC

from baserow.contrib.automation.workflows.operations import AutomationWorkflowOperationType
from baserow.contrib.automation.operations import AutomationOperationType


class AutomationNodeOperationType(AutomationOperationType, ABC):
    context_scope_name = "automation_node"


class ListAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.list_nodes"
    object_scope_name = "automation_node"


class CreateAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.create_node"


class UpdateAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.update"


class DeleteAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.delete"

class RestoreAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.restore"
