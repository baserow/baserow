from typing import TYPE_CHECKING, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType
from baserow_enterprise.assistant.types import WorkflowNavigationType

from . import utils
from .types import WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def get_list_workflows_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int], dict[str, list[dict]]]:
    """
    List all workflows in an automation.
    """

    def list_workflows(automation_id: int) -> dict[str, Any]:
        """
        List all workflows in an automation application.

        :param automation_id: The ID of the automation application
        :return: Dictionary with workflows list
        """

        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(_("Listing workflows..."))

        automation = utils.get_automation(automation_id, user, workspace)
        workflows = AutomationWorkflowService().list_workflows(user, automation.id)

        return {
            "workflows": [
                {"id": w.id, "name": w.name, "state": w.state} for w in workflows
            ]
        }

    return list_workflows


def get_create_workflows_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, list[WorkflowCreate]], dict[str, list[dict]]]:
    """
    Create new workflows.
    """

    def create_workflows(
        automation_id: int, workflows: list[WorkflowCreate]
    ) -> dict[str, Any]:
        """
        Create one or more workflows in an automation.

        :param automation_id: The automation application ID
        :param workflows: List of workflows to create
        :return: Dictionary with created workflows
        """

        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(_("Creating workflows..."))

        created = []

        automation = utils.get_automation(automation_id, user, workspace)
        for wf in workflows:
            with transaction.atomic():
                orm_workflow = utils.create_workflow(user, automation, wf)
                created.append(
                    {
                        "id": orm_workflow.id,
                        "name": orm_workflow.name,
                        "state": orm_workflow.state,
                    }
                )
        # Navigate to the last created workflow
        tool_helpers.navigate_to(
            WorkflowNavigationType(
                type="automation-workflow",
                automation_id=automation.id,
                workflow_id=orm_workflow.id,
                workflow_name=orm_workflow.name,
            )
        )

        return {"created_workflows": created}

    return create_workflows


# ============================================================================
# TOOL TYPE REGISTRY
# ============================================================================


class ListWorkflowsToolType(AssistantToolType):
    type = "list_workflows"

    @classmethod
    def get_tool(cls, user, workspace, tool_helpers):
        return get_list_workflows_tool(user, workspace, tool_helpers)


class CreateWorkflowsToolType(AssistantToolType):
    type = "create_workflows"

    @classmethod
    def get_tool(cls, user, workspace, tool_helpers):
        return get_create_workflows_tool(user, workspace, tool_helpers)
