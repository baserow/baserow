from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.models import Workspace
from baserow.core.service import CoreService

from .types import WorkflowCreate


def get_automation(
    automation_id: int, user: AbstractUser, workspace: Workspace
) -> Automation:
    """Get automation with permission check."""

    base_queryset = Automation.objects.filter(workspace=workspace)
    automation = CoreService().get_application(
        user, automation_id, base_queryset=base_queryset
    )
    return automation


def get_workflow(
    workflow_id: int, user: AbstractUser, workspace: Workspace
) -> AutomationWorkflow:
    """Get workflow with permission check."""

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    if workflow.automation.workspace_id != workspace.id:
        raise ValueError("Workflow not in workspace")
    return workflow


def create_workflow(
    user: AbstractUser,
    automation: Automation,
    workflow: WorkflowCreate,
) -> AutomationWorkflow:
    """
    Creates a new workflow in the given automation based on the provided definition.
    """

    orm_wf = AutomationWorkflowService().create_workflow(
        user, automation.id, workflow.name
    )

    node_mapping = {}

    # First create the trigger node
    orm_service_data = workflow.trigger.to_orm_service_dict()
    node_type = automation_node_type_registry.get(workflow.trigger.type)
    orm_trigger = AutomationNodeService().create_node(
        user,
        node_type,
        orm_wf,
        label=workflow.trigger.label,
        service=orm_service_data,
    )

    node_mapping[workflow.trigger.ref] = node_mapping[orm_trigger.id] = (
        orm_trigger,
        workflow.trigger,
    )

    for node in workflow.nodes:
        orm_service_data = node.to_orm_service_dict()
        reference_node_id, output = node.to_orm_reference_node(node_mapping)
        node_type = automation_node_type_registry.get(node.type)
        orm_node = AutomationNodeService().create_node(
            user,
            node_type,
            orm_wf,
            reference_node_id=reference_node_id,
            output=output,
            label=node.label,
            service=orm_service_data,
        )
        node_mapping[node.ref] = node_mapping[orm_node.id] = (orm_node, node)

    return orm_wf
