from baserow.contrib.automation.tools import automations, workflows
from baserow.core.mcp.groups import GROUP_AUTOMATION_EDIT, GROUP_AUTOMATION_READ
from baserow.core.mcp.registries import FunctionMCPTool


class ListWorkflowsMcpTool(FunctionMCPTool):
    type = "list_workflows"
    group = GROUP_AUTOMATION_READ
    title = "List workflows"
    read_only = True
    function = workflows.list_workflows


class CreateAutomationMcpTool(FunctionMCPTool):
    type = "create_automation"
    group = GROUP_AUTOMATION_EDIT
    title = "Create an automation"
    read_only = False
    destructive = False
    function = automations.create_automation


class UpdateAutomationMcpTool(FunctionMCPTool):
    type = "update_automation"
    group = GROUP_AUTOMATION_EDIT
    title = "Rename an automation"
    read_only = False
    destructive = True
    function = automations.update_automation


class CreateWorkflowsMcpTool(FunctionMCPTool):
    type = "create_workflows"
    group = GROUP_AUTOMATION_EDIT
    title = "Create workflows"
    read_only = False
    destructive = False
    function = workflows.create_workflows


class PublishWorkflowMcpTool(FunctionMCPTool):
    type = "publish_workflow"
    group = GROUP_AUTOMATION_EDIT
    title = "Publish a workflow"
    read_only = False
    destructive = True
    function = workflows.publish_workflow


class PauseWorkflowMcpTool(FunctionMCPTool):
    type = "pause_workflow"
    group = GROUP_AUTOMATION_EDIT
    title = "Pause a workflow"
    read_only = False
    destructive = False
    function = workflows.pause_workflow
