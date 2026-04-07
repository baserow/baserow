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
from .types import ActionNodeCreate, NodeUpdate, WorkflowCreate


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


def list_nodes(
    ctx: RunContext[AssistantDeps],
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow to list nodes for.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List nodes in a workflow in execution order.

    WHEN to use: Inspect the nodes in a workflow, find node IDs before updating or deleting.
    WHAT it does: Lists all nodes (trigger + actions) in graph traversal order with id, label, and type.
    RETURNS: Nodes array with id, label, type.
    DO NOT USE when: You already have the node IDs you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    tool_helpers.update_status(_("Listing nodes..."))

    workflow = helpers.get_workflow(workflow_id, user, workspace)
    nodes = helpers.get_nodes_in_order(user, workflow)

    return {"nodes": nodes}


def add_nodes(
    ctx: RunContext[AssistantDeps],
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow to add nodes to.")
    ],
    nodes: Annotated[
        list[ActionNodeCreate],
        Field(
            description="Nodes to add. previous_node_ref can be an existing node ID (as string) or a temp ref from an earlier node in this list."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add action/router nodes to an existing workflow.

    WHEN to use: User wants to insert or append nodes in an existing workflow — e.g. add a router between trigger and action, or add a new action after an existing one.
    WHAT it does: Creates new nodes attached to existing ones. Use previous_node_ref with the string ID of an existing node (e.g. "49") or a temp ref of a node being created in the same call.
    RETURNS: Created nodes array with id, label, type.
    DO NOT USE when: You want to create an entirely new workflow — use create_workflows instead.
    HOW: Use list_nodes first to find the existing node IDs, then specify previous_node_ref to place new nodes. Use router_edge_label when attaching to a router branch.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not nodes:
        return {"created_nodes": []}

    tool_helpers.update_status(_("Adding nodes to workflow..."))

    workflow = helpers.get_workflow(workflow_id, user, workspace)

    with transaction.atomic():
        created_nodes, node_mapping = helpers.add_nodes_to_workflow(
            user, workflow, nodes, tool_helpers
        )

    # Generate formulas for nodes that need them
    for orm_node, node_create in [(n, nodes[i]) for i, n in enumerate(created_nodes)]:
        formulas = node_create.get_formulas_to_create(orm_node)
        if formulas:
            node_create.apply_direct_values(orm_node.service)
            tool_helpers.update_status(
                _(
                    "Generating formulas for node '%(label)s'..."
                    % {"label": orm_node.label}
                )
            )
            with transaction.atomic():
                try:
                    agents.update_single_node_formulas(
                        node_create, orm_node, tool_helpers
                    )
                except Exception:
                    from loguru import logger

                    logger.exception(
                        "Failed to generate formulas for node {}", orm_node.id
                    )

    return {
        "created_nodes": [
            {"id": n.id, "label": n.get_label(), "type": n.get_type().type}
            for n in created_nodes
        ]
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


def update_nodes(
    ctx: RunContext[AssistantDeps],
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow containing the nodes.")
    ],
    nodes: Annotated[
        list[NodeUpdate],
        Field(
            description="List of node updates, each with a node_id and properties to change."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update automation node labels and service configuration.

    WHEN to use: User wants to rename a node, change email subject/body, update slack channel, etc.
    WHAT it does: Updates node label and/or service config. Supports $formula: prefix for dynamic values.
    RETURNS: Updated node IDs and any errors.
    DO NOT USE when: You need to change a node's type — delete and recreate it instead.
    HOW: Use list_workflows first to find the workflow and node IDs.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not nodes:
        return {"updated_nodes": []}

    # Verify workflow belongs to workspace
    helpers.get_workflow(workflow_id, user, workspace)

    updated = []
    errors = []
    nodes_needing_formulas = []

    with transaction.atomic():
        for node_update in nodes:
            tool_helpers.raise_if_cancelled()
            try:
                orm_node = helpers.update_node(
                    user, workspace, node_update, tool_helpers
                )
                updated.append({"node_id": orm_node.id, "label": orm_node.label})

                # Check if any fields need formula generation
                formulas = node_update.get_formulas_to_update(orm_node)
                if formulas:
                    nodes_needing_formulas.append((node_update, orm_node, formulas))
            except Exception as e:
                errors.append(f"Error updating node {node_update.node_id}: {e}")

    # Apply direct values and generate formulas outside the main transaction
    for node_update, orm_node, formulas in nodes_needing_formulas:
        node_update.apply_direct_values(orm_node.service)
        tool_helpers.update_status(
            _("Generating formulas for node '%(label)s'..." % {"label": orm_node.label})
        )
        with transaction.atomic():
            try:
                agents.update_single_node_formulas(node_update, orm_node, tool_helpers)
            except Exception as exc:
                from loguru import logger

                logger.exception(
                    "Failed to generate formulas for node {}: {}", orm_node.id, exc
                )

    result: dict[str, Any] = {"updated_nodes": updated}
    if errors:
        result["errors"] = errors
    return result


def delete_nodes(
    ctx: RunContext[AssistantDeps],
    node_ids: Annotated[
        list[int],
        Field(description="List of node IDs to delete."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Delete automation nodes.

    WHEN to use: User wants to remove nodes from a workflow.
    WHAT it does: Deletes the specified automation nodes.
    RETURNS: Deleted node IDs and any errors.
    DO NOT USE when: You want to modify a node — use update_nodes instead.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    if not node_ids:
        return {"deleted_node_ids": []}

    deleted = []
    errors = []

    for node_id in node_ids:
        tool_helpers.raise_if_cancelled()
        tool_helpers.update_status(
            _("Deleting node %(node_id)s...") % {"node_id": node_id}
        )
        try:
            helpers.delete_node(user, workspace, node_id)
            deleted.append(node_id)
        except Exception as e:
            errors.append(f"Error deleting node {node_id}: {e}")

    result: dict[str, Any] = {"deleted_node_ids": deleted}
    if errors:
        result["errors"] = errors
    return result


TOOL_FUNCTIONS = [
    list_workflows,
    list_nodes,
    create_workflows,
    add_nodes,
    update_nodes,
    delete_nodes,
]
automation_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)

ROUTING_RULES = """\
- switch_mode: switch domain if task needs tools not in the current mode.
- create_workflows: use {{ node.ref }} for node refs, $formula: prefix for dynamic field values.
- add_nodes: insert/append nodes. Use list_nodes first to find existing node IDs."""
