from typing import List

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
)
from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)
from baserow.contrib.automation.workflows.operations import (
    DeleteAutomationWorkflowOperationType,
    PublishAutomationWorkflowOperationType,
    ReadAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.signals import (
    automation_workflow_created,
    automation_workflow_deleted,
    automation_workflow_published,
    automation_workflow_updated,
    automation_workflows_reordered,
)
from baserow.contrib.integrations.core.models import CoreHTTPTriggerService
from baserow.contrib.integrations.core.signals import core_http_webhook_service_updated
from baserow.core.utils import generate_hash
from baserow.ws.tasks import broadcast_to_group, broadcast_to_permitted_users


@receiver(automation_workflow_created)
def workflow_created(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow.automation.workspace_id,
            ReadAutomationWorkflowOperationType.type,
            AutomationWorkflowObjectScopeType.type,
            workflow.id,
            {
                "type": "automation_workflow_created",
                "workflow": AutomationWorkflowSerializer(workflow).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_workflow_deleted)
def workflow_deleted(
    sender, automation: Automation, workflow_id: int, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            automation.workspace_id,
            DeleteAutomationWorkflowOperationType.type,
            AutomationObjectScopeType.type,
            automation.id,
            {
                "type": "automation_workflow_deleted",
                "workflow_id": workflow_id,
                "automation_id": automation.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_workflow_updated)
def workflow_updated(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow.automation.workspace_id,
            UpdateAutomationWorkflowOperationType.type,
            AutomationWorkflowObjectScopeType.type,
            workflow.id,
            {
                "type": "automation_workflow_updated",
                "workflow": AutomationWorkflowSerializer(workflow).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_workflow_published)
def workflow_published(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    workflow = workflow.automation.published_from
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow.automation.workspace_id,
            PublishAutomationWorkflowOperationType.type,
            AutomationWorkflowObjectScopeType.type,
            workflow.id,
            {
                "type": "automation_workflow_published",
                "workflow": AutomationWorkflowSerializer(workflow).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_workflows_reordered)
def workflow_reordered(
    sender, automation: Automation, order: List[int], user: AbstractUser, **kwargs
):
    # Hashing all values here to not expose real ids of workflows a user
    # might not have access to
    order = [generate_hash(o) for o in order]
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            automation.workspace_id,
            {
                "type": "automation_workflows_reordered",
                # A user might also not have access to the automation itself
                "automation_id": generate_hash(automation.id),
                "order": order,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_workflow_published)
def clear_http_trigger_node_errors(
    sender, workflow: AutomationWorkflow, user: AbstractUser, **kwargs
):
    webhook_service_content_type = ContentType.objects.get_for_model(
        CoreHTTPTriggerService
    )
    for node in workflow.automation_workflow_nodes.filter(
        service__content_type=webhook_service_content_type
    ):
        core_http_webhook_service_updated.send(sender, service=node.service.specific)
