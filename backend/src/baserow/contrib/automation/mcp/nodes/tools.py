from baserow.contrib.automation.tools import nodes
from baserow.core.mcp.groups import (
    GROUP_AUTOMATION_DELETE,
    GROUP_AUTOMATION_EDIT,
    GROUP_AUTOMATION_READ,
)
from baserow.core.mcp.registries import FunctionMCPTool


class ListNodesMcpTool(FunctionMCPTool):
    type = "list_nodes"
    group = GROUP_AUTOMATION_READ
    title = "List workflow nodes"
    read_only = True
    function = nodes.list_nodes


class AddNodesMcpTool(FunctionMCPTool):
    type = "add_nodes"
    group = GROUP_AUTOMATION_EDIT
    title = "Add workflow nodes"
    read_only = False
    destructive = False
    function = nodes.add_nodes


class UpdateNodesMcpTool(FunctionMCPTool):
    type = "update_nodes"
    group = GROUP_AUTOMATION_EDIT
    title = "Update workflow nodes"
    read_only = False
    destructive = True
    function = nodes.update_nodes


class DeleteNodesMcpTool(FunctionMCPTool):
    type = "delete_nodes"
    group = GROUP_AUTOMATION_DELETE
    title = "Delete workflow nodes"
    read_only = False
    destructive = True
    function = nodes.delete_nodes
