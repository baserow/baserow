from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.contrib.automation.tools import nodes as shared_nodes
from baserow.contrib.automation.tools import workflows as shared_workflows
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.shared import require_payload
from baserow_enterprise.assistant.types import WorkflowNavigationType

from . import agents, helpers, reconciliation
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

    ctx.deps.tool_helpers.update_status(_("Listing workflows..."))

    (automation,) = shared_workflows.list_workflows(
        ctx.deps.tool_context(), automation_id
    )["automations"]
    return {"workflows": automation["workflows"]}


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

    ctx.deps.tool_helpers.update_status(_("Listing nodes..."))

    # No output schemas: they are long, and Kuma's formula generator reads them
    # itself.
    return {
        "nodes": shared_nodes.describe_workflow_nodes(
            ctx.deps.tool_context(), workflow_id, with_output_schema=False
        )
    }


def _shared_call(function, *args):
    """Call a shared tool, turning a request it rejects into a retry."""

    try:
        return function(*args)
    except DjangoValidationError as exc:
        raise ModelRetry(" ".join(exc.messages))


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
    RETURNS: Created nodes with id, label, type, plus formula_errors if needed.
    DO NOT USE when: You want to create an entirely new workflow — use create_workflows instead.
    HOW: Use list_nodes first to find the existing node IDs, then specify previous_node_ref to place new nodes. Use router_edge_label when attaching to a router branch.
    REQUIRED: `workflow_id` and `nodes` must arrive in the same call. The ID says where to act; the payload says what to create. A call carrying only the ID creates nothing and is rejected.
    """

    require_payload("add_nodes", "nodes", nodes)
    ctx.deps.tool_helpers.update_status(_("Adding nodes to workflow..."))

    tool_context = ctx.deps.tool_context()
    result = _shared_call(shared_nodes.add_nodes, tool_context, workflow_id, nodes)
    # The nodes are committed now, so the formula generator runs outside them.
    formula_errors = agents.repair_formula_errors(
        tool_context,
        ctx.deps.tool_helpers,
        result.pop("formula_errors", []),
        {node["id"]: node["ref"] for node in result["created_nodes"]},
    )
    result["created_nodes"] = [
        {key: node[key] for key in ("id", "label", "type")}
        for node in result["created_nodes"]
    ]
    if formula_errors:
        result["formula_errors"] = formula_errors
    return result


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
    WHAT it does: Reuses exact-name matches and creates missing workflows with a trigger and action/router nodes. Reused workflows return actual nodes and next_steps when their node sequence differs.
    RETURNS: Created and reused workflows, plus formula_errors if needed.
    HOW: Each workflow needs exactly one trigger and one or more actions/routers. Know the table_id and field_ids for row-based triggers and actions. Every update_row or delete_row action also requires row_id. To act on the triggering row, set row_id to "$formula: ID of the row that fired the trigger". Never omit it or use a made-up row ID.

    ## Workflow Structure

    Each workflow has a trigger (the starting event) and action nodes (tasks to perform).
    Nodes execute in sequence. previous_node_ref connects nodes using their ref.
    For dynamic field values, describe the previous node and property after
    $formula:; the tool compiles that description against the actual node data.

    ## Dynamic Values with $formula:

    Any string field marked "A literal or a formula" can use dynamic values.
    Prefix with '$formula:' + a natural-language description to auto-generate a formula
    from context data. Otherwise the value is used as a literal.
    - {"field_id": 123, "value": "$formula: the customer name from the trigger data"}
    - {"field_id": 456, "value": "$formula: today's date"}
    - {"field_id": 789, "value": "pending"}  ← literal, no prefix
    """

    user = ctx.deps.user
    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_workflows", "workflows", workflows)

    tool_context = ctx.deps.tool_context()
    automation = helpers.get_automation(automation_id, user, ctx.deps.workspace)
    creation = _shared_call(
        shared_workflows.create_workflows_in_automation,
        tool_context,
        automation,
        workflows,
    )
    plan = creation.plan

    run_created = tool_helpers.request_context.setdefault(
        reconciliation.RUN_CREATED_WORKFLOWS, {}
    )
    created_workflows = []
    formula_errors = []
    errors = list(creation.failed)
    for workflow_spec, workflow, node_creation in creation.created:
        created_workflows.append(shared_workflows.describe_workflow(workflow))
        errors.extend(node_creation.errors)
        # The workflow is committed now, so the formula generator runs outside it.
        workflow_errors = agents.repair_formula_errors(
            tool_context,
            tool_helpers,
            node_creation.formula_errors,
            {node.id: ref for ref, node in node_creation.nodes},
        )
        formula_errors.extend(workflow_errors)
        if not workflow_errors and not node_creation.errors:
            run_created[workflow.id] = reconciliation.VerifiedWorkflowCreation(
                request=workflow_spec.model_dump(),
                configuration=reconciliation.workflow_configuration_fingerprint(
                    user, workflow
                ),
            )

    if creation.created:
        last_created_workflow = creation.created[-1][1]
        tool_helpers.navigate_to(
            WorkflowNavigationType(
                type="automation-workflow",
                automation_id=automation.id,
                workflow_id=last_created_workflow.id,
                workflow_name=last_created_workflow.name,
            )
        )

    requested_by_name = {spec.name: spec for spec in plan.requested}
    verified_workflow_ids = {
        workflow.id
        for workflow in plan.to_reuse
        if (verified := run_created.get(workflow.id)) is not None
        and verified.request == requested_by_name[workflow.name].model_dump()
        and verified.configuration
        == reconciliation.workflow_configuration_fingerprint(user, workflow)
    }

    reused_workflows = reconciliation.describe_reused_workflows(user, plan.to_reuse)
    result: dict[str, Any] = {
        "created_workflows": created_workflows,
        "reused_workflows": reused_workflows,
    }
    result.update(
        reconciliation.reused_workflow_report(
            plan.requested, reused_workflows, verified_workflow_ids
        )
    )
    if errors:
        result["errors"] = errors
    if formula_errors:
        result["formula_errors"] = formula_errors
    return result


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
    Update automation node labels, service configuration and router conditions.

    WHEN to use: User wants to rename a node, change email subject/body, update slack channel, change a router branch condition, etc.
    WHAT it does: Updates node label and/or service config. Supports $formula: prefix for dynamic values.
    RETURNS: Updated node IDs and any update or formula errors.
    DO NOT USE when: You need to change a node's type — delete and recreate it instead.
    HOW: Use list_nodes first to find the node IDs.
    """

    if not nodes:
        return {"updated_nodes": []}

    tool_context = ctx.deps.tool_context()
    result = _shared_call(shared_nodes.update_nodes, tool_context, workflow_id, nodes)
    # The updates are committed now, so the formula generator runs outside them.
    formula_errors = agents.repair_formula_errors(
        tool_context, ctx.deps.tool_helpers, result.pop("formula_errors", [])
    )
    if formula_errors:
        result["formula_errors"] = formula_errors
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

    if not node_ids:
        return {"deleted_node_ids": []}

    return shared_nodes.delete_nodes(ctx.deps.tool_context(), node_ids)


TOOL_FUNCTIONS = [
    list_workflows,
    list_nodes,
    create_workflows,
    add_nodes,
    update_nodes,
    delete_nodes,
]
automation_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)
