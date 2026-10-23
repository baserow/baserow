"""
Node tools shared by the clients that act for a user.
"""

from dataclasses import dataclass, field
from typing import Annotated, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger
from pydantic import Field

from baserow.contrib.automation.nodes.actions import (
    CreateAutomationNodeActionType,
    DeleteAutomationNodeActionType,
    UpdateAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.operations import (
    ReadAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools.formulas import formula_error
from baserow.contrib.automation.tools.types import (
    ActionNodeCreate,
    NodeRefs,
    NodeUpdate,
    ServiceValues,
    TriggerNodeCreate,
)
from baserow.contrib.automation.tools.workflows import get_workflow_in_workspace
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.database.fields.models import Field as DatabaseField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.mcp.exceptions import (
    INTERNAL_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    to_mcp_error,
)
from baserow.core.tools import ToolContext


def get_node_in_workspace(ctx: ToolContext, node_id: int) -> AutomationNode:
    """
    Get a node of a workflow in the context's workspace.

    :raises AutomationNodeDoesNotExist: When the node is missing, trashed or in
        another workspace.
    :raises PermissionException: When the user may not read it.
    """

    node = AutomationNodeHandler().get_node(
        node_id,
        base_queryset=AutomationNode.objects.filter(
            workflow__automation__workspace=ctx.workspace
        ),
    )
    CoreHandler().check_permissions(
        ctx.user,
        ReadAutomationNodeOperationType.type,
        workspace=ctx.workspace,
        context=node,
    )
    return node


def _child_ids(info: dict[str, Any]) -> list[int]:
    children = info.get("children")
    if isinstance(children, dict):
        return [node_id for ids in children.values() for node_id in ids]
    return list(children) if isinstance(children, list) else []


def nodes_in_order(
    user: AbstractUser, workflow: AutomationWorkflow
) -> list[tuple[AutomationNode, AutomationNode | None, str]]:
    """
    The nodes of a workflow in execution order: the trigger, then each node after
    the one before it, a container's children before the nodes that follow it.

    :returns: Each node with the node it follows (None for the trigger) and the
        output of that node it is attached to ("" for the default one).
    """

    nodes = {
        node.id: node for node in AutomationNodeService().get_nodes(user, workflow)
    }
    graph = workflow.get_graph().graph
    ordered: list[tuple[AutomationNode, AutomationNode | None, str]] = []
    visited: set[int] = set()

    def walk(node_id: int, previous: AutomationNode | None, output: str) -> None:
        if node_id in visited or node_id not in nodes:
            return
        visited.add(node_id)
        node = nodes[node_id]
        ordered.append((node, previous, output))
        info = graph.get(str(node_id), {})
        for child_id in _child_ids(info):
            walk(child_id, node, "")
        # A router's branches in their order, the default one last, as the editor
        # shows them.
        branch_order = [edge["uid"] for edge in router_edges(node)] + [""]
        next_outputs = sorted(
            info.get("next", {}).items(),
            key=lambda item: (
                branch_order.index(item[0]) if item[0] in branch_order else 0
            ),
        )
        for next_output, next_ids in next_outputs:
            for next_id in next_ids:
                walk(next_id, node, next_output)

    trigger_id = graph.get("0")
    if trigger_id is not None:
        walk(trigger_id, None, "")
    return ordered


def router_edges(node: AutomationNode) -> list[dict[str, str]]:
    """The branches of a router node in order, empty for other nodes."""

    if node.get_type().type != "router":
        return []
    return [
        {"label": edge.label, "uid": str(edge.uid)}
        for edge in node.service.specific.edges.all()
    ]


def _compact_properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = {}
    for key, prop in (schema.get("properties") or {}).items():
        entry = {"title": prop.get("title", key), "type": prop.get("type")}
        if prop.get("type") == "object" and prop.get("properties"):
            entry["properties"] = _compact_properties(prop)
        elif prop.get("type") == "array" and isinstance(prop.get("items"), dict):
            items = prop["items"]
            if items.get("properties"):
                entry["items"] = _compact_properties(items)
        properties[key] = entry
    return properties


def output_schema(node: AutomationNode) -> dict[str, Any]:
    """
    What a node outputs, for the formulas of the nodes after it: the formula path
    to its data and its properties, keyed as the path expects.
    """

    service = node.service.specific
    service_type = service.get_type()
    schema = service_type.generate_schema(service) or {}
    if schema.get("type") == "array":
        schema = schema.get("items") or {}
    path = f"previous_node.{node.id}"
    if service_type.returns_list:
        path += ".0"
    return {"formula_path": path, "properties": _compact_properties(schema)}


def describe_node(
    node: AutomationNode,
    previous: AutomationNode | None = None,
    output: str = "",
) -> dict[str, Any]:
    """A node as the node tools return it."""

    description: dict[str, Any] = {
        "id": node.id,
        "label": node.label,
        "type": node.get_type().type,
    }
    if previous is not None:
        description["previous_node_ref"] = str(previous.id)
        if output:
            labels = {edge["uid"]: edge["label"] for edge in router_edges(previous)}
            description["router_edge_label"] = labels.get(output, "")
    edges = router_edges(node)
    if edges:
        description["edges"] = edges
    return description


def describe_workflow_nodes(
    ctx: ToolContext, workflow_id: int, with_output_schema: bool = True
) -> list[dict[str, Any]]:
    """
    The nodes of a workflow of the context's workspace in execution order.

    :param with_output_schema: Whether to add each node's output schema, which
        reads the schema of every node's service.
    """

    workflow = get_workflow_in_workspace(ctx, workflow_id)
    nodes = []
    for node, previous, output in nodes_in_order(ctx.user, workflow):
        description = describe_node(node, previous, output)
        if with_output_schema:
            description["output_schema"] = output_schema(node)
        nodes.append(description)
    return nodes


def list_nodes(
    ctx: ToolContext,
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow to list nodes for.")
    ],
) -> dict[str, Any]:
    """
    List the nodes of a workflow in execution order, the trigger first. Each node
    has its id, label and type, the node it follows (previous_node_ref) and, on a
    router branch, the branch label. A router lists its branches. output_schema
    says what a node outputs: a later node's formula reads a property with
    get('<formula_path>.<property key>').
    """

    return {"nodes": describe_workflow_nodes(ctx, workflow_id)}


# ---------------------------------------------------------------------------
# Writing nodes
# ---------------------------------------------------------------------------


def item_error_message(exc: Exception) -> str:
    """
    The message for one node that failed while the others go on. Call it from the
    ``except`` block, so an unexpected error is logged with its traceback.
    """

    message = to_mcp_error(exc)
    if message is None and not isinstance(exc, AttributeError):
        if isinstance(exc, ObjectDoesNotExist):
            message = NOT_FOUND_MESSAGE
        elif type(exc).__module__.startswith("baserow"):
            # Baserow's own errors (AutomationNodeNotDeletable, ...) say what the
            # caller did wrong.
            message = str(exc) or type(exc).__name__
    if message is None:
        logger.exception("Unexpected error in an automation tool item: {}", exc)
        return INTERNAL_ERROR_MESSAGE
    return message


def check_tables_in_workspace(ctx: ToolContext, table_ids: set[int]) -> None:
    """
    Check that the tables of row triggers and row actions are tables of the
    context's workspace the user can see.

    :raises Table.DoesNotExist: When one is not.
    """

    if not table_ids:
        return
    found = set(
        TableHandler()
        .list_workspace_tables(ctx.user, ctx.workspace)
        .filter(id__in=table_ids)
        .values_list("id", flat=True)
    )
    missing = sorted(table_ids - found)
    if missing:
        raise Table.DoesNotExist(f"Table {missing[0]} does not exist.")


def table_field_ids() -> Callable[[int], set[int]]:
    """Returns the ids of a table's fields, reading each table once."""

    cache: dict[int, set[int]] = {}

    def field_ids(table_id: int) -> set[int]:
        if table_id not in cache:
            cache[table_id] = set(
                DatabaseField.objects.filter(table_id=table_id).values_list(
                    "id", flat=True
                )
            )
        return cache[table_id]

    return field_ids


def node_refs(user: AbstractUser, workflow: AutomationWorkflow) -> NodeRefs:
    """The nodes of a workflow that a new node can follow, by their ID."""

    refs = NodeRefs()
    for node in AutomationNodeService().get_nodes(user, workflow):
        edges = router_edges(node)
        refs.add(
            str(node.id),
            node.id,
            # The first branch wins when labels repeat, as in the editor's order.
            {edge["label"]: edge["uid"] for edge in reversed(edges)}
            if node.get_type().type == "router"
            else None,
        )
    return refs


def check_node_refs(refs: NodeRefs, nodes: list[ActionNodeCreate]) -> None:
    """
    Check that every node follows a known node, before anything is written.

    :raises DjangoValidationError: Naming the first unknown ref or branch.
    """

    for node in nodes:
        refs.resolve(node.previous_node_ref, node.router_edge_label)
        if node.ref in refs:
            raise DjangoValidationError(
                f"ref '{node.ref}' is already the ref or ID of another node. Give "
                "each new node its own ref."
            )
        refs.add(node.ref, None, node.router_edges())


@dataclass
class NodeCreation:
    """The nodes a call created, and the values it could not set."""

    nodes: list[tuple[str, AutomationNode]] = field(default_factory=list)
    formula_errors: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "ref": ref,
                "id": node.id,
                "label": node.label,
                "type": node.get_type().type,
            }
            for ref, node in self.nodes
        ]

    def add_values(self, node: AutomationNode, values: ServiceValues) -> None:
        self.formula_errors.extend(
            formula_error(node, exc, **target) for exc, target in values.invalid
        )
        self.errors.extend(
            f"Node {node.id} ({node.label}): {error}" for error in values.errors
        )


def create_node(
    ctx: ToolContext,
    workflow: AutomationWorkflow,
    spec: TriggerNodeCreate | ActionNodeCreate,
    refs: NodeRefs,
    creation: NodeCreation,
    field_ids: Callable[[int], set[int]],
) -> AutomationNode:
    """
    Create a node after the node its definition names, and note it in ``refs`` so
    later nodes can follow it.
    """

    ctx.update_status(_("Creating node %(label)s...") % {"label": spec.label})
    values = ServiceValues(field_ids, refs=refs.ids())
    data: dict[str, Any] = {"label": spec.label}
    if isinstance(spec, TriggerNodeCreate):
        data["service"] = spec.to_orm_service_dict()
    else:
        data["reference_node_id"], data["output"] = refs.resolve(
            spec.previous_node_ref, spec.router_edge_label
        )
        data["service"] = spec.to_orm_service_dict(values)
    node = CreateAutomationNodeActionType.do(
        ctx.user, automation_node_type_registry.get(spec.type), workflow, data
    )
    edges = spec.router_edges() if isinstance(spec, ActionNodeCreate) else None
    refs.add(spec.ref, node.id, edges)
    creation.nodes.append((spec.ref, node))
    creation.add_values(node, values)
    return node


def node_table_ids(nodes: list[TriggerNodeCreate | ActionNodeCreate]) -> set[int]:
    table_ids = set()
    for node in nodes:
        table_id = (
            node.table_id() if isinstance(node, TriggerNodeCreate) else node.table_id
        )
        if table_id is not None:
            table_ids.add(table_id)
    return table_ids


def add_nodes(
    ctx: ToolContext,
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow to add nodes to.")
    ],
    nodes: Annotated[
        list[ActionNodeCreate],
        Field(
            description="The nodes to add, in order. previous_node_ref is the ID of "
            "a node of the workflow, as a string, or the ref of a node earlier in "
            "this list."
        ),
    ],
) -> dict[str, Any]:
    """
    Add action and router nodes to a workflow, after existing nodes or after each
    other. Use list_nodes to find the IDs of the nodes to attach to, and
    router_edge_label to attach to a router branch. A value that takes a formula
    is a formula when it looks like one (get(...), concat(...), ...), otherwise a
    literal; to store text that looks like a formula, send it as a quoted string
    such as 'Call now()'. A formula reads an earlier node with
    get('previous_node.<node id>...'), and a node defined earlier in the call can
    be named by its ref there. A valid formula is stored as written. An invalid
    one leaves that value empty and is returned in formula_errors with the
    parser's message: fix it with update_nodes. Nothing is written when a
    previous_node_ref or branch is unknown, or a ref is used twice.
    """

    if not nodes:
        raise DjangoValidationError("nodes must hold at least one node to add.")

    workflow = get_workflow_in_workspace(ctx, workflow_id)
    check_tables_in_workspace(ctx, node_table_ids(nodes))
    refs = node_refs(ctx.user, workflow)
    check_node_refs(refs.copy(), nodes)

    creation = NodeCreation()
    field_ids = table_field_ids()
    with transaction.atomic():
        for node in nodes:
            create_node(ctx, workflow, node, refs, creation, field_ids)

    result: dict[str, Any] = {"created_nodes": creation.describe()}
    if creation.errors:
        result["errors"] = creation.errors
    if creation.formula_errors:
        result["formula_errors"] = creation.formula_errors
    return result


def update_node(
    ctx: ToolContext,
    workflow: AutomationWorkflow,
    node_update: NodeUpdate,
    field_ids: Callable[[int], set[int]],
    as_formulas: bool = False,
    refs: dict[str, int] | None = None,
) -> tuple[AutomationNode, ServiceValues]:
    """
    Update a node of the workflow.

    :param as_formulas: Take every value as a formula, for a caller that wrote
        them as formulas.
    :param refs: The ID of nodes by the ref they were created under, for
        formulas that name them by ref.

    :returns: The node as it is now, and the values that could not be set.
    :raises AutomationNodeDoesNotExist: When the node is not in the workflow.
    """

    try:
        node = get_node_in_workspace(ctx, node_update.node_id)
    except PermissionException:
        # Not found, like a missing node, so the result doesn't tell which.
        raise AutomationNodeDoesNotExist(node_update.node_id)
    if node.workflow_id != workflow.id:
        raise AutomationNodeDoesNotExist(node_update.node_id)
    if node_update.table_id is not None:
        check_tables_in_workspace(ctx, {node_update.table_id})

    values = ServiceValues(field_ids, as_formulas, refs=refs, updating=True)
    data: dict[str, Any] = {}
    if node_update.label is not None:
        data["label"] = node_update.label
    service = node_update.to_update_service_dict(node, values)
    if service is not None:
        data["service"] = service
    if data:
        node = UpdateAutomationNodeActionType.do(ctx.user, node.id, data)
    return node, values


def _lock_nodes(workflow: AutomationWorkflow, node_ids: list[int]) -> None:
    """
    Lock the requested nodes of the workflow before the first change, in id
    order, so concurrent calls take the locks in one order.
    """

    list(
        AutomationNode.objects.filter(id__in=node_ids, workflow=workflow)
        .select_for_update(of=("self",))
        .order_by("id")
        .values_list("id", flat=True)
    )


def update_nodes(
    ctx: ToolContext,
    workflow_id: Annotated[
        int, Field(description="The ID of the workflow the nodes are in.")
    ],
    nodes: Annotated[
        list[NodeUpdate],
        Field(
            description="The node updates, each with a node_id and the values to change."
        ),
    ],
) -> dict[str, Any]:
    """
    Update nodes of a workflow: their label and settings, a row action's table
    and field values, and the conditions of a router's branches. A node's type and
    a trigger's settings cannot change. Values not given keep theirs. Formulas
    work as in add_nodes, except that a value with an invalid formula keeps what
    it had; the formula is returned in formula_errors. A node that fails is
    reported in errors and the others are still updated. If the user may not
    change a node, nothing is changed.
    """

    if not nodes:
        raise DjangoValidationError("nodes must hold at least one node update.")

    workflow = get_workflow_in_workspace(ctx, workflow_id)
    updated = []
    errors = []
    formula_errors = []
    field_ids = table_field_ids()

    with transaction.atomic():
        _lock_nodes(workflow, [node_update.node_id for node_update in nodes])
        for node_update in nodes:
            ctx.update_status(
                _("Updating node %(node_id)s...") % {"node_id": node_update.node_id}
            )
            try:
                # A savepoint, so a failed node leaves the transaction usable.
                with transaction.atomic():
                    node, values = update_node(ctx, workflow, node_update, field_ids)
            except PermissionException:
                raise
            except Exception as exc:
                errors.append(
                    f"Error updating node {node_update.node_id}: "
                    f"{item_error_message(exc)}"
                )
                continue
            updated.append({"node_id": node.id, "label": node.label})
            creation = NodeCreation()
            creation.add_values(node, values)
            errors.extend(creation.errors)
            formula_errors.extend(creation.formula_errors)

    result: dict[str, Any] = {"updated_nodes": updated}
    if errors:
        result["errors"] = errors
    if formula_errors:
        result["formula_errors"] = formula_errors
    return result


def delete_nodes(
    ctx: ToolContext,
    node_ids: Annotated[
        list[int], Field(description="The IDs of the nodes to delete.")
    ],
) -> dict[str, Any]:
    """
    Move nodes to the trash, from where they can be restored. A router with nodes
    on its branches cannot be deleted. A node that fails is reported in errors and
    the others are still deleted.
    """

    if not node_ids:
        raise DjangoValidationError("node_ids must hold at least one node ID.")

    deleted = []
    errors = []

    with transaction.atomic():
        for node_id in node_ids:
            ctx.update_status(_("Deleting node %(node_id)s...") % {"node_id": node_id})
            try:
                # Not found whether the node is missing, elsewhere or hidden, so
                # the result doesn't tell which.
                try:
                    get_node_in_workspace(ctx, node_id)
                except PermissionException:
                    raise AutomationNodeDoesNotExist(node_id)
                with transaction.atomic():
                    DeleteAutomationNodeActionType.do(ctx.user, node_id)
            except PermissionException:
                errors.append(
                    f"Permission denied for node {node_id}; it was not deleted."
                )
                continue
            except Exception as exc:
                errors.append(
                    f"Error deleting node {node_id}: {item_error_message(exc)}"
                )
                continue
            deleted.append(node_id)

    result: dict[str, Any] = {"deleted_node_ids": deleted}
    if errors:
        result["errors"] = errors
    return result
