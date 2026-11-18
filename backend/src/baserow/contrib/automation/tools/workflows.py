"""
Workflow tools shared by the clients that act for a user.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.api.errors import ERROR_UNTRUSTED_CONTENT_CANNOT_BE_PUBLISHED
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.tools.types import WorkflowCreate
from baserow.contrib.automation.workflows.actions import (
    CreateAutomationWorkflowActionType,
    UpdateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    PublishAutomationWorkflowOperationType,
    ReadAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.exceptions import (
    PermissionException,
    UntrustedContentCannotBePublished,
)
from baserow.core.handler import CoreHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.tools import ToolContext, tool_execution
from baserow.core.tools.applications import (
    get_application_in_workspace,
    visible_applications,
)
from baserow.core.tools.errors import ToolInputError, item_error_message


def get_automation_in_workspace(ctx: ToolContext, automation_id: int) -> Automation:
    """
    Get an automation of the context's workspace.

    :raises ApplicationDoesNotExist: When the automation is missing, trashed, in
        another workspace or hidden from the user.
    """

    return get_application_in_workspace(ctx, automation_id, Automation)


def get_workflow_in_workspace(ctx: ToolContext, workflow_id: int) -> AutomationWorkflow:
    """
    Get a workflow of an automation in the context's workspace.

    :raises AutomationWorkflowDoesNotExist: When the workflow is missing, trashed
        or in another workspace.
    :raises PermissionException: When the user may not read it.
    """

    workflow = AutomationWorkflowHandler().get_workflow(
        workflow_id,
        base_queryset=AutomationWorkflow.objects.filter(
            automation__workspace=ctx.workspace
        ),
    )
    CoreHandler().check_permissions(
        ctx.user,
        ReadAutomationWorkflowOperationType.type,
        workspace=ctx.workspace,
        context=workflow,
    )
    return workflow


def describe_workflow(workflow: AutomationWorkflow) -> dict[str, Any]:
    """
    The id, name and state of a workflow. Publishing copies a workflow, so its state
    is the one of its published version, as the REST API reports it, and a workflow
    without one is a draft.

    :param workflow: The workflow. One from `annotate_published_workflow_data` runs
        no query.
    """

    return {
        "id": workflow.id,
        "name": workflow.name,
        "state": AutomationWorkflowHandler()
        .get_state(workflow, with_cache=False)
        .value,
    }


@tool_execution
def list_workflows(
    ctx: ToolContext,
    automation_id: Annotated[
        int | None,
        Field(
            description="The ID of the automation to list workflows for. null lists "
            "every automation in the workspace."
        ),
    ] = None,
) -> dict[str, Any]:
    """
    List the automations of the workspace with their workflows: id, name and state
    (draft, live, paused or disabled). A draft has never been published and doesn't
    run. The other states are those of the last published version, so a live workflow
    can have later edits that aren't running yet. Pass automation_id to list one
    automation. Use list_nodes to see the nodes of a workflow.
    """

    if automation_id is None:
        automations = list(visible_applications(ctx, ["automation"]))
    else:
        automations = [get_automation_in_workspace(ctx, automation_id)]

    workflows = CoreHandler().filter_queryset(
        ctx.user,
        ReadAutomationWorkflowOperationType.type,
        AutomationWorkflowHandler().annotate_published_workflow_data(
            AutomationWorkflow.objects.filter(automation__in=automations)
        ),
        workspace=ctx.workspace,
    )
    by_automation: dict[int, list[dict[str, Any]]] = {}
    for workflow in workflows.order_by("order", "id"):
        by_automation.setdefault(workflow.automation_id, []).append(
            describe_workflow(workflow)
        )

    return {
        "automations": [
            {
                "id": automation.id,
                "name": automation.name,
                "workflows": by_automation.get(automation.id, []),
            }
            for automation in automations
        ]
    }


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


@dataclass
class WorkflowCreation:
    """What a create_workflows call did."""

    plan: WorkflowCreationPlan
    created: list[tuple[WorkflowCreate, AutomationWorkflow, Any]]
    """Each created workflow with its definition and its ``NodeCreation``."""

    failed: list[str] = field(default_factory=list)
    """Why each workflow that could not be saved wasn't."""

    def to_response(self, user: AbstractUser) -> dict[str, Any]:
        from baserow.contrib.automation.tools.nodes import describe_node, nodes_in_order

        result: dict[str, Any] = {
            "created_workflows": [
                {**describe_workflow(workflow), "nodes": creation.describe()}
                for _spec, workflow, creation in self.created
            ],
            "reused_workflows": [
                {
                    **describe_workflow(workflow),
                    "nodes": [
                        describe_node(node, previous, output)
                        for node, previous, output in nodes_in_order(user, workflow)
                    ],
                }
                for workflow in self.plan.to_reuse
            ],
        }
        errors = [
            *self.failed,
            *(error for *_, creation in self.created for error in creation.errors),
        ]
        if errors:
            result["errors"] = errors
        formula_errors = self.formula_errors
        if formula_errors:
            result["formula_errors"] = formula_errors
        return result

    @property
    def formula_errors(self) -> list[dict[str, Any]]:
        return [
            error for *_, creation in self.created for error in creation.formula_errors
        ]


def create_workflows_in_automation(
    ctx: ToolContext, automation: Automation, workflows: list[WorkflowCreate]
) -> WorkflowCreation:
    """
    Create the workflows of an automation that don't exist yet by name, each in
    its own transaction. Everything is checked before the first one is written.

    :raises DjangoValidationError: When two definitions share a name, or a node
        follows an unknown ref or branch.
    :raises Table.DoesNotExist: When a row trigger or action names a table that
        is not in the workspace.
    """

    from baserow.contrib.automation.tools.nodes import (
        NodeCreation,
        check_node_refs,
        check_tables_in_workspace,
        create_node,
        node_table_ids,
        table_field_ids,
    )
    from baserow.contrib.automation.tools.types import NodeRefs

    if not workflows:
        raise DjangoValidationError("workflows must hold at least one workflow.")

    existing = CoreHandler().filter_queryset(
        ctx.user,
        ReadAutomationWorkflowOperationType.type,
        AutomationWorkflowHandler().annotate_published_workflow_data(
            AutomationWorkflow.objects.filter(automation=automation)
        ),
        workspace=ctx.workspace,
    )
    plan = plan_workflow_creation(workflows, existing)
    if plan.conflicting_names:
        names = ", ".join(plan.conflicting_names)
        raise DjangoValidationError(
            f"Conflicting workflow definitions use the same name: {names}. "
            "Submit one definition per workflow name."
        )
    for spec in plan.to_create:
        refs = NodeRefs()
        refs.add(spec.trigger.ref, None)
        check_node_refs(refs, spec.nodes)
    check_tables_in_workspace(
        ctx,
        node_table_ids(
            [node for spec in plan.to_create for node in (spec.trigger, *spec.nodes)]
        ),
    )

    created = []
    failed = []
    field_ids = table_field_ids()
    for spec in plan.to_create:
        ctx.update_status(_("Creating workflow %(name)s...") % {"name": spec.name})
        creation = NodeCreation()
        try:
            with transaction.atomic():
                workflow = CreateAutomationWorkflowActionType.do(
                    ctx.user, automation.id, {"name": spec.name}
                )
                refs = NodeRefs()
                for node in (spec.trigger, *spec.nodes):
                    create_node(ctx, workflow, node, refs, creation, field_ids)
        except PermissionException:
            raise
        except Exception as exc:
            # The workflows saved before stay, with their formula errors.
            failed.append(
                f"Workflow {spec.name} was not created: {item_error_message(exc)}"
            )
            continue
        created.append((spec, workflow, creation))
    return WorkflowCreation(plan=plan, created=created, failed=failed)


@tool_execution
def create_workflows(
    ctx: ToolContext,
    automation_id: Annotated[
        int,
        Field(
            description="The ID of the automation to create workflows in. "
            "create_automation returns the ID of a new one."
        ),
    ],
    workflows: Annotated[
        list[WorkflowCreate],
        Field(description="The workflows to create, each with a trigger and nodes."),
    ],
) -> dict[str, Any]:
    """
    Create workflows, each with a trigger and the nodes after it. Created workflows
    are drafts and don't run until published with publish_workflow. Nodes follow
    each other through previous_node_ref, the ref of an earlier node in the same
    workflow, and router_edge_label attaches a node to a router branch. A row
    trigger or row action needs the table_id and field IDs of a table in the
    workspace. update_row and delete_row need a row_id; after a row trigger it is
    usually get('previous_node.<trigger ref>.0.id').

    A value that takes a formula is a formula when it looks like one (get(...),
    concat(...), if(...), ...), otherwise a literal; to store text that looks like
    a formula, send it as a quoted string such as 'Call now()'. Read an earlier
    node's output with get('previous_node.<node>...'), where <node> is the ref of
    a node earlier in the same workflow or a node ID: list_nodes shows each node's
    output paths, and a path a node doesn't output is invalid. A row trigger's
    fields are read as get('previous_node.<trigger>.0.field_<id>'). A router
    condition is always a formula. A valid formula is stored as written. An
    invalid one leaves that value empty and is returned in formula_errors with
    the node and the reason: fix it with update_nodes.

    A workflow whose name already exists is not created again nor changed: it is
    returned in reused_workflows with its nodes. Nothing is written when two
    definitions share a name, or a previous_node_ref or branch is unknown. A
    workflow that fails to save is reported in errors and the others are kept.
    """

    automation = get_automation_in_workspace(ctx, automation_id)
    return create_workflows_in_automation(ctx, automation, workflows).to_response(
        ctx.user
    )


def _nodes_in_order(ctx: ToolContext, workflow: AutomationWorkflow) -> list:
    from baserow.contrib.automation.tools.nodes import nodes_in_order

    return [
        node
        for node, *_ in nodes_in_order(
            ctx.user,
            workflow,
            AutomationNodeHandler().get_nodes(workflow, with_cache=False),
        )
    ]


def _raise_if_never_runs(nodes: list) -> None:
    if not nodes or not nodes[0].get_type().is_workflow_trigger:
        raise ToolInputError(
            "This workflow has no trigger, so it would never run. Nothing was "
            "published."
        )
    if not any(node.get_type().is_workflow_action for node in nodes[1:]):
        raise ToolInputError(
            "This workflow has no action after its trigger, so it would do nothing. "
            "Nothing was published."
        )


def check_workflow_can_run(
    ctx: ToolContext, published_workflow: AutomationWorkflow
) -> list[str]:
    """
    Checks what can be told about a published copy of a workflow before it goes
    live. This isn't a full check: a node can still fail when it runs.

    :param published_workflow: The copy `AutomationWorkflowService.publish` made.
        Warnings name the draft nodes it was copied from.
    :raises ToolInputError: When the workflow can never do anything.
    :return: A warning for each node its type finds misconfigured.
    """

    nodes = _nodes_in_order(ctx, published_workflow)
    _raise_if_never_runs(nodes)

    draft_node_ids = getattr(published_workflow, "draft_node_ids", {})
    warnings = []
    for node in nodes:
        node_type = node.get_type()
        node_id = draft_node_ids.get(node.id, node.id)
        try:
            node_type.raise_if_misconfigured(node)
        except ServiceImproperlyConfiguredDispatchException as exc:
            consequence = (
                "It never fires."
                if node_type.is_workflow_trigger
                else "Every run fails here."
            )
            warnings.append(f"Node {node_id} ({node.label}): {exc} {consequence}")
            continue
        for notice in node_type.get_publish_notices(node):
            warnings.append(f"Node {node_id} ({node.label}): {notice}")
    return warnings


@tool_execution
def publish_workflow(
    ctx: ToolContext,
    workflow_id: Annotated[
        int,
        Field(
            description="The ID of the workflow to publish, from create_workflows or "
            "list_workflows."
        ),
    ],
) -> dict[str, Any]:
    """
    Publish a workflow, so it runs when its trigger fires. Effects are real and start
    straight away: rows written or deleted, emails sent, HTTP calls made. Get the
    user's approval first. A run that fails keeps what earlier nodes did.

    A copy of the current workflow is live when this returns and the workflow keeps
    its ID. Later edits don't reach the live version until it is published again,
    which replaces that version. Republishing makes a paused or disabled workflow live
    again with a fresh error count. pause_workflow stops a live workflow.

    A workflow with no trigger, or no action after its trigger, is refused and the
    version already live stays live. warnings lists nodes found to be misconfigured,
    which doesn't mean the others are sound. Imported content must be reviewed and
    trusted in the app before it can be published.
    """

    workflow = get_workflow_in_workspace(ctx, workflow_id)
    CoreHandler().check_permissions(
        ctx.user,
        PublishAutomationWorkflowOperationType.type,
        workspace=ctx.workspace,
        context=workflow.automation,
    )
    # Refuse an empty draft before paying for a copy. The copy is checked again,
    # since the draft can change while it is made.
    _raise_if_never_runs(_nodes_in_order(ctx, workflow))
    try:
        with transaction.atomic():
            published = AutomationWorkflowService().publish(ctx.user, workflow)
            # The copy is what goes live, whatever changed in the draft while it was
            # made. Refusing it rolls the publication back, so the previous copy
            # stays live.
            warnings = check_workflow_can_run(ctx, published)
    except UntrustedContentCannotBePublished as exc:
        raise ToolInputError(ERROR_UNTRUSTED_CONTENT_CANNOT_BE_PUBLISHED[2]) from exc
    result: dict[str, Any] = {
        "published_workflow": {
            "id": workflow.id,
            "name": workflow.name,
            "state": WorkflowState(published.state).value,
        }
    }
    if warnings:
        result["warnings"] = warnings
    return result


@tool_execution
def pause_workflow(
    ctx: ToolContext,
    workflow_id: Annotated[
        int,
        Field(
            description="The ID of the workflow to pause, from create_workflows or "
            "list_workflows."
        ),
    ],
) -> dict[str, Any]:
    """
    Pause a live workflow, so its trigger no longer starts runs. Events while it is
    paused aren't replayed. A run already under way isn't stopped. publish_workflow
    makes it live again by publishing the current draft, with any edits made since,
    not the paused version. changed is false when it was already paused. A workflow
    that was never published or was disabled is refused.
    """

    workflow = get_workflow_in_workspace(ctx, workflow_id)
    CoreHandler().check_permissions(
        ctx.user,
        UpdateAutomationWorkflowOperationType.type,
        workspace=ctx.workspace,
        context=workflow,
    )
    with transaction.atomic():
        # Waits for a publish in progress, so what it leaves live is what gets paused.
        published = AutomationWorkflowHandler().get_published_workflow_for_update(
            workflow
        )
        if published is None:
            raise ToolInputError(
                "This workflow has never been published, so it isn't running and "
                "there is nothing to pause."
            )
        if published.state == WorkflowState.DISABLED:
            raise ToolInputError(
                "This workflow was disabled after too many failed runs, so it isn't "
                "running and stays disabled. Publishing it again makes it live."
            )
        changed = published.state != WorkflowState.PAUSED
        if changed:
            UpdateAutomationWorkflowActionType.do(
                ctx.user, workflow.id, {"state": WorkflowState.PAUSED}
            )
    return {"paused_workflow": describe_workflow(workflow), "changed": changed}
