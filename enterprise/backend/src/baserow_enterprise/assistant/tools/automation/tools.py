from typing import TYPE_CHECKING, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

import udspy

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


def get_workflow_tool_factory(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, list[WorkflowCreate]], dict[str, list[dict]]]:
    def create_workflows(
        automation_id: int, workflows: list[WorkflowCreate]
    ) -> dict[str, Any]:
        """
        Create one or more workflows in an automation. Always use {{ node.ref }} to
        reference previous nodes values inside the workflow.

        :param automation_id: The automation application ID
        :param workflows: List of workflows to create
        :return: Dictionary with created workflows
        """

        nonlocal user, workspace, tool_helpers

        created = []

        automation = utils.get_automation(automation_id, user, workspace)
        for wf in workflows:
            with transaction.atomic():
                orm_workflow, node_mapping = utils.create_workflow(
                    user, automation, wf, tool_helpers
                )
                created.append(
                    {
                        "id": orm_workflow.id,
                        "name": orm_workflow.name,
                        "state": orm_workflow.state,
                    }
                )

            # In separate transactions, try to update the formulas inside the workflow,
            # so we don't block the main creation if something goes wrong here.
            utils.update_workflow_formulas(wf, node_mapping, tool_helpers)

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

    def load_workflow_automation_tools():
        """
        TOOL LOADER: Loads tools to manage workflows in an automation.

        After calling this loader, you will have access to:
        - create_workflows: Create workflows with triggers, actions, and routers

        Use this when you need to create workflows in an automation but don't have the tool.
        """  # noqa: W505

        @udspy.module_callback
        def _load_workflow_automation_tools(context):
            nonlocal user, workspace, tool_helpers

            observation = ["New tools are now available.\n"]

            create_tool = udspy.Tool(create_workflows)
            new_tools = [create_tool]
            observation.append(
                "- Use `create_workflows` to create workflows in an automation."
            )

            # Re-initialize the module with the new tools for the next iteration
            context.module.init_module(tools=context.module._tools + new_tools)
            return "\n".join(observation)

        return _load_workflow_automation_tools

    return load_workflow_automation_tools


# ============================================================================
# TOOL TYPE REGISTRY
# ============================================================================


class ListWorkflowsToolType(AssistantToolType):
    type = "list_workflows"

    @classmethod
    def get_tool(cls, user, workspace, tool_helpers):
        return get_list_workflows_tool(user, workspace, tool_helpers)


class WorkflowToolFactoryToolType(AssistantToolType):
    type = "workflow_tool_factory"

    @classmethod
    def get_tool(cls, user, workspace, tool_helpers):
        return get_workflow_tool_factory(user, workspace, tool_helpers)
