from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.automation.api.nodes.serializers import AutomationNodeSerializer
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.object_scopes import AutomationNodeObjectScopeType
from baserow.contrib.automation.nodes.operations import (
    ListAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
    automation_node_updated,
)
from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(automation_node_created)
def node_created(sender, node: AutomationNode, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            node.workflow.automation.workspace_id,
            ReadAutomationNodeOperationType.type,
            AutomationNodeObjectScopeType.type,
            node.id,
            {
                "type": "automation_node_created",
                "node": AutomationNodeSerializer(node).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_node_deleted)
def node_deleted(
    sender, workflow: AutomationWorkflow, node_id: int, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow.automation.workspace_id,
            ListAutomationNodeOperationType.type,
            AutomationWorkflowObjectScopeType.type,
            workflow.id,
            {
                "type": "automation_node_deleted",
                "node_id": node_id,
                "workflow_id": workflow.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_node_updated)
def node_updated(sender, node: AutomationNode, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            node.workflow.automation.workspace_id,
            ReadAutomationNodeOperationType.type,
            AutomationNodeObjectScopeType.type,
            node.id,
            {
                "type": "automation_node_updated",
                "node": AutomationNodeSerializer(node).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )
