from abc import ABC

from baserow.contrib.automation.operations import AutomationOperationType
from baserow.contrib.automation.workflows.operations import (
    AutomationWorkflowOperationType,
)


class AutomationNodeOperationType(AutomationOperationType, ABC):
    context_scope_name = "automation_node"


class ListAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.list_nodes"
    object_scope_name = "automation_node"


class OrderAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.order_nodes"


class CreateAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.create_node"


class ReadAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.read"


class UpdateAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.update"


class DeleteAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.delete"


class RestoreAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.restore"


class DuplicateAutomationNodeOperationType(AutomationNodeOperationType):
    type = "automation.node.duplicate"
