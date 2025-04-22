from baserow.contrib.automation.workflows.operations import AutomationWorkflowOperationType


class ListAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.list_nodes"
    object_scope_name = "automation_node"


class CreateAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.create_node"
