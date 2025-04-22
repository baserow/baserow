from baserow.contrib.automation.workflows.operations import AutomationWorkflowOperationType


class ListAutomationWorkflowNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.list_automation_nodes"
    object_scope_name = "automation_workflow_node"


class CreateAutomationNodeOperationType(AutomationWorkflowOperationType):
    type = "automation.workflow.create_node"
