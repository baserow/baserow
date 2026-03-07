from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.types import WorkflowNavigationType

from . import agents, helpers
from .types import WorkflowCreate


def list_workflows(
    ctx: RunContext[AssistantDeps],
    automation_id: Annotated[
        int, Field(description="The ID of the automation to list workflows for.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List workflows in an automation.

    WHEN to use: Check existing workflows in an automation, or find workflow IDs before creating new ones.
    WHAT it does: Lists all workflows in an automation with their id, name, and state.
    RETURNS: Workflows array with id, name, state.
    DO NOT USE when: You already have the workflow IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    tool_helpers.update_status(_("Listing workflows..."))

    automation = helpers.get_automation(automation_id, user, workspace)
    workflows = AutomationWorkflowService().list_workflows(user, automation.id)

    return {
        "workflows": [{"id": w.id, "name": w.name, "state": w.state} for w in workflows]
    }


def create_workflows(
    ctx: RunContext[AssistantDeps],
    automation_id: Annotated[
        int, Field(description="The ID of the automation to create workflows in.")
    ],
    workflows: Annotated[
        list[WorkflowCreate],
        Field(
            description="List of workflows to create, each with a trigger and action nodes."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create workflows with triggers and action nodes.

    WHEN to use: User wants automated workflows with triggers and action nodes.
    WHAT it does: Creates workflows with a trigger and action/router/iterator nodes. Use {{ node.ref }} for referencing values from previous nodes.
    RETURNS: Created workflows with id, name, state.
    DO NOT USE when: Workflows with those names already exist — check with list_workflows first.
    HOW: Each workflow needs exactly one trigger and one or more actions/routers. Use {{ node.ref }} syntax to reference previous node values in action formulas. Know the table_id and field_ids for row-based triggers and actions.

    ## Workflow Structure

    Each workflow has a trigger (the starting event) and action nodes (tasks to perform).
    Nodes execute in sequence. Use {{ node.ref }} template syntax to reference
    values from previous nodes.

    ## Dynamic Values with $formula:

    Any string field marked "Supports $formula:" can use dynamic values.
    Prefix with '$formula:' + a natural-language description to auto-generate a formula
    from context data. Otherwise the value is used as a literal.
    - {"field_id": 123, "value": "$formula: the customer name from the trigger data"}
    - {"field_id": 456, "value": "$formula: today's date"}
    - {"field_id": 789, "value": "pending"}  ← literal, no prefix
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not workflows:
        return {"created_workflows": []}

    created = []

    automation = helpers.get_automation(automation_id, user, workspace)
    for wf in workflows:
        tool_helpers.raise_if_cancelled()
        with transaction.atomic():
            orm_workflow, node_mapping = helpers.create_workflow(
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
        agents.update_workflow_formulas(wf, node_mapping, tool_helpers)

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


TOOL_FUNCTIONS = [list_workflows, create_workflows]
automation_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
