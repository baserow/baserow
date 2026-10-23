"""
Permission-checked accessors for the automation assistant tools.
"""

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.tools.nodes import nodes_in_order
from baserow.contrib.automation.tools.workflows import (
    get_automation_in_workspace,
    get_workflow_in_workspace,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.models import Workspace
from baserow.core.tools import ToolContext


def get_automation(
    automation_id: int, user: AbstractUser, workspace: Workspace
) -> Automation:
    """Fetch an automation scoped to the user's workspace."""

    return get_automation_in_workspace(ToolContext(user, workspace), automation_id)


def get_workflow(
    workflow_id: int, user: AbstractUser, workspace: Workspace
) -> AutomationWorkflow:
    """Fetch a workflow scoped to the user's workspace."""

    return get_workflow_in_workspace(ToolContext(user, workspace), workflow_id)


def get_nodes_in_order(user: AbstractUser, workflow: AutomationWorkflow) -> list[dict]:
    """Return the nodes of a workflow in execution order, with id, label and type."""

    return [
        {"id": node.id, "label": node.label, "type": node.get_type().type}
        for node, _previous, _output in nodes_in_order(user, workflow)
    ]
