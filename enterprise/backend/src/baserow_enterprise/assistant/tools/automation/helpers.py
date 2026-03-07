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

from .types import WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers


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
        reference_node_id, output = node.to_orm_reference_node(node_mapping)
        orm_node = _create_node(
            user, orm_wf, node, tool_helpers,
            reference_node_id=reference_node_id, output=output,
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
