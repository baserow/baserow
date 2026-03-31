"""
Shared helpers for the automation assistant tools.

Contains permission-checked accessors and the workflow creation orchestrator
used by ``tools.py`` and ``agents.py``.
"""

from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.models import Workspace
from baserow.core.service import CoreService

from .types import NodeUpdate, WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers

    from .types import ActionNodeCreate


def get_automation(
    automation_id: int, user: AbstractUser, workspace: Workspace
) -> Automation:
    """Fetch an automation scoped to the user's workspace."""

    base_queryset = Automation.objects.filter(workspace=workspace)
    return CoreService().get_application(
        user, automation_id, base_queryset=base_queryset
    )


def get_workflow(
    workflow_id: int, user: AbstractUser, workspace: Workspace
) -> AutomationWorkflow:
    """Fetch a workflow with a workspace-level permission check."""

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    if workflow.automation.workspace_id != workspace.id:
        raise ValueError("Workflow not in workspace")
    return workflow


def get_nodes_in_order(user: AbstractUser, workflow: AutomationWorkflow) -> list[dict]:
    """
    Return the nodes of a workflow in graph traversal order.

    Walks the workflow graph starting from the trigger, following ``next``
    edges (all outputs) and ``children`` to produce a flat, ordered list.
    """

    nodes = AutomationNodeService().get_nodes(user, workflow)
    node_map = {n.id: n for n in nodes}
    graph = workflow.get_graph().graph

    trigger_id = graph.get("0")
    if trigger_id is None:
        return []

    ordered_ids: list[int] = []
    visited: set[int] = set()

    def walk(node_id: int):
        if node_id in visited or node_id not in node_map:
            return
        visited.add(node_id)
        ordered_ids.append(node_id)
        info = graph.get(str(node_id), {})
        # Follow children first (for container nodes like iterators)
        for child_id in info.get("children", []):
            walk(child_id)
        # Then follow next edges in order
        for output_uid, next_ids in info.get("next", {}).items():
            for nid in next_ids:
                walk(nid)

    walk(trigger_id)

    result = []
    for nid in ordered_ids:
        node = node_map[nid]
        node_type = node.get_type()
        entry = {
            "id": node.id,
            "label": node.get_label(),
            "type": node_type.type,
        }
        result.append(entry)

    return result


def add_nodes_to_workflow(
    user: AbstractUser,
    workflow: AutomationWorkflow,
    nodes: list["ActionNodeCreate"],
    tool_helpers: "ToolHelpers",
) -> tuple[list[Any], dict[int | str, Any]]:
    """
    Add action nodes to an existing workflow.

    The ``previous_node_ref`` on each node can reference:
    - An existing node ID as a string (e.g. "49")
    - A temp ref from an earlier node in the same ``nodes`` list

    Returns a list of created ORM nodes and the node mapping.
    """

    # Seed the mapping with existing nodes in the workflow
    existing_nodes = AutomationNodeService().get_nodes(user, workflow)
    node_mapping: dict[int | str, Any] = {}
    for n in existing_nodes:
        # Create a stub for the node_create part that has type and edges info
        stub = _ExistingNodeStub(n)
        node_mapping[str(n.id)] = (n, stub)
        node_mapping[n.id] = (n, stub)

    created = []
    for node in nodes:
        tool_helpers.raise_if_cancelled()
        reference_node_id, output = node.to_orm_reference_node(node_mapping)
        orm_node = _create_node(
            user,
            workflow,
            node,
            tool_helpers,
            reference_node_id=reference_node_id,
            output=output,
        )
        node_mapping[node.ref] = node_mapping[orm_node.id] = (orm_node, node)
        created.append(orm_node)

    return created, node_mapping


class _EdgeStub:
    """Bridges ORM edge ``uid`` to the ``_uid`` attribute expected by ``to_orm_reference_node``."""

    def __init__(self, orm_edge):
        self.label = orm_edge.label
        self._uid = str(orm_edge.uid)


class _ExistingNodeStub:
    """
    Lightweight stub exposing ``type`` and ``edges`` from an existing ORM node,
    so ``ActionNodeCreate.to_orm_reference_node`` can resolve router edge labels.
    """

    def __init__(self, orm_node):
        self.type = orm_node.get_type().type
        self.edges = []
        if self.type == "router" and hasattr(orm_node.service, "specific"):
            service = orm_node.service.specific
            if hasattr(service, "edges"):
                self.edges = [_EdgeStub(e) for e in service.edges.all()]


def create_workflow(
    user: AbstractUser,
    automation: Automation,
    workflow: "WorkflowCreate",
    tool_helpers: "ToolHelpers",
) -> tuple[AutomationWorkflow, dict[int | str, Any]]:
    """
    Create a workflow with its trigger and action nodes.

    Returns the ORM workflow and a mapping of ``{ref_or_id: (orm_node, node_create)}``
    for every created node, usable by downstream formula generation.
    """

    tool_helpers.update_status(
        _("Creating workflow '%(name)s'..." % {"name": workflow.name})
    )

    orm_wf = AutomationWorkflowService().create_workflow(
        user, automation.id, workflow.name
    )

    node_mapping: dict[int | str, Any] = {}

    # -- Trigger --
    orm_trigger = _create_node(user, orm_wf, workflow.trigger, tool_helpers)
    node_mapping[workflow.trigger.ref] = node_mapping[orm_trigger.id] = (
        orm_trigger,
        workflow.trigger,
    )

    # -- Action / router / iterator nodes --
    for node in workflow.nodes:
        try:
            reference_node_id, output = node.to_orm_reference_node(node_mapping)
        except ValueError as exc:
            from pydantic_ai import ModelRetry

            raise ModelRetry(str(exc)) from exc
        orm_node = _create_node(
            user,
            orm_wf,
            node,
            tool_helpers,
            reference_node_id=reference_node_id,
            output=output,
        )
        node_mapping[node.ref] = node_mapping[orm_node.id] = (orm_node, node)

    return orm_wf, node_mapping


def _create_node(user, workflow, node_create, tool_helpers, **extra_kwargs):
    """Create a single automation node (trigger or action)."""

    tool_helpers.update_status(
        _("Creating node '%(label)s'..." % {"label": node_create.label})
    )
    node_type = automation_node_type_registry.get(node_create.type)
    return AutomationNodeService().create_node(
        user,
        node_type,
        workflow,
        label=node_create.label,
        service=node_create.to_orm_service_dict(),
        **extra_kwargs,
    )


def update_node(
    user: "AbstractUser",
    workspace: "Workspace",
    node_update: "NodeUpdate",
    tool_helpers: "ToolHelpers",
):
    """
    Update an automation node's label and/or service config.

    :param user: The acting user.
    :param workspace: Workspace for permission check.
    :param node_update: The update definition.
    :param tool_helpers: Provides status updates.
    :returns: The updated ORM node.
    """

    node = AutomationNodeService().get_node(user, node_update.node_id)
    if node.workflow.automation.workspace_id != workspace.id:
        raise ValueError("Node not in workspace")

    kwargs = {}
    if node_update.label is not None:
        kwargs["label"] = node_update.label

    node_type = node.service.get_type().type if node.service else None
    service_dict = node_update.to_update_service_dict(node_type) if node_type else None
    if service_dict is not None:
        kwargs["service"] = service_dict

    if kwargs:
        tool_helpers.update_status(
            _("Updating node '%(label)s'..." % {"label": node.label})
        )
        AutomationNodeService().update_node(user, node.id, **kwargs)

    return AutomationNodeService().get_node(user, node_update.node_id)


def delete_node(
    user: "AbstractUser",
    workspace: "Workspace",
    node_id: int,
):
    """
    Delete an automation node.

    :param user: The acting user.
    :param workspace: Workspace for permission check.
    :param node_id: ID of the node to delete.
    """

    node = AutomationNodeService().get_node(user, node_id)
    if node.workflow.automation.workspace_id != workspace.id:
        raise ValueError("Node not in workspace")
    AutomationNodeService().delete_node(user, node_id)
