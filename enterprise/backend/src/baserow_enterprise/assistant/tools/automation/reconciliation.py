from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.workflows.models import AutomationWorkflow

from . import helpers
from .types import WorkflowCreate
from .types.node import CANONICAL_TO_SHORT_TYPE


@dataclass(frozen=True)
class WorkflowCreationPlan:
    """Canonical workflow requests and their exact-name matches."""

    requested: list[WorkflowCreate]
    to_create: list[WorkflowCreate]
    to_reuse: list[AutomationWorkflow]
    conflicting_names: list[str]


def _canonical_workflow_requests(
    requested: Sequence[WorkflowCreate],
) -> tuple[list[WorkflowCreate], list[str]]:
    canonical: list[WorkflowCreate] = []
    by_name: dict[str, WorkflowCreate] = {}
    conflicting_names: list[str] = []

    for workflow in requested:
        first_request = by_name.get(workflow.name)
        if first_request is None:
            canonical.append(workflow)
            by_name[workflow.name] = workflow
        # model_dump ignores private attrs such as RouterEdgeCreate._uid.
        elif (
            workflow.model_dump() != first_request.model_dump()
            and workflow.name not in conflicting_names
        ):
            conflicting_names.append(workflow.name)

    return canonical, conflicting_names


def plan_workflow_creation(
    requested: Sequence[WorkflowCreate], existing: Iterable[AutomationWorkflow]
) -> WorkflowCreationPlan:
    """
    Match requested workflows to exact-name workflows.

    :param requested: The requested workflow definitions.
    :param existing: The workflows already present in the automation.
    :return: The canonical requests split into workflows to create and reuse.
    """

    canonical, conflicting_names = _canonical_workflow_requests(requested)
    existing_by_name = {workflow.name: workflow for workflow in existing}
    to_create: list[WorkflowCreate] = []
    to_reuse: list[AutomationWorkflow] = []

    for workflow in canonical:
        existing_workflow = existing_by_name.get(workflow.name)
        if existing_workflow is not None:
            to_reuse.append(existing_workflow)
            continue

        to_create.append(workflow)

    return WorkflowCreationPlan(
        requested=canonical,
        to_create=to_create,
        to_reuse=to_reuse,
        conflicting_names=conflicting_names,
    )


def _short_node_type(node_type: str) -> str:
    return CANONICAL_TO_SHORT_TYPE.get(node_type, node_type)


def describe_reused_workflows(
    user: AbstractUser, workflows: Sequence[AutomationWorkflow]
) -> list[dict[str, Any]]:
    """
    Describe reused workflows and their current nodes, with short node types.

    :param user: The acting user.
    :param workflows: The reused workflows to describe.
    :return: One dict per workflow with id, name, state and ordered nodes.
    """

    return [
        {
            "id": workflow.id,
            "name": workflow.name,
            "state": workflow.state,
            "nodes": [
                {**node, "type": _short_node_type(node["type"])}
                for node in helpers.get_nodes_in_order(user, workflow)
            ],
        }
        for workflow in workflows
    ]


def _requested_node_sequence(workflow: WorkflowCreate) -> list[dict[str, str]]:
    return [
        {
            "label": workflow.trigger.label,
            "type": _short_node_type(workflow.trigger.type),
        },
        *[
            {"label": node.label, "type": _short_node_type(node.type)}
            for node in workflow.nodes
        ],
    ]


def _actual_node_sequence(nodes: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"label": node["label"], "type": _short_node_type(node["type"])}
        for node in nodes
    ]


def _incomplete_reused_workflows(
    requested_by_name: dict[str, WorkflowCreate], actual: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    incomplete = []
    for workflow in actual:
        requested_nodes = _requested_node_sequence(requested_by_name[workflow["name"]])
        if _actual_node_sequence(workflow["nodes"]) != requested_nodes:
            incomplete.append(
                {
                    "id": workflow["id"],
                    "name": workflow["name"],
                    "requested_nodes": requested_nodes,
                }
            )
    return incomplete


def reused_workflow_report(
    requested: Sequence[WorkflowCreate], actual: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """
    Build follow-up guidance for reused workflows.

    :param requested: The requested workflow definitions.
    :param actual: The reused workflows as described by
        describe_reused_workflows.
    :return: Incomplete workflows and next_steps keys, or an empty dict when
        nothing was reused.
    """

    if not actual:
        return {}

    requested_by_name = {workflow.name: workflow for workflow in requested}
    incomplete = _incomplete_reused_workflows(requested_by_name, actual)

    report: dict[str, Any] = {}
    if incomplete:
        report["incomplete_reused_workflows"] = incomplete
        structure_steps = (
            "Exact-name workflows were reused, but their nodes in "
            "reused_workflows do not match the requested_nodes sequence. If "
            "the trigger matches, call add_nodes for missing actions using "
            "actual node IDs as previous_node_ref, or update_nodes for "
            "changed nodes. "
        )
    else:
        structure_steps = ""

    report["next_steps"] = structure_steps + (
        "Node labels and types alone do not verify trigger or action "
        "configuration of the reused_workflows. Compare the request with "
        "identical verified prior create_workflows arguments; otherwise "
        "reapply every action's requested configuration with update_nodes "
        "using the actual node IDs. Trigger settings cannot be read or "
        "updated by the available assistant tools. If identical verified "
        "prior arguments are absent, report that exact limitation and do "
        "not claim the workflow is complete."
    )
    return report
