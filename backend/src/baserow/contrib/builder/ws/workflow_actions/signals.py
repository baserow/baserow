from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.api.workflow_actions.serializers import (
    BuilderWorkflowActionSerializer,
)
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.object_scopes import BuilderPageObjectScopeType
from baserow.contrib.builder.workflow_actions import signals as workflow_action_signals
from baserow.contrib.builder.workflow_actions.object_scopes import (
    BuilderWorkflowActionScopeType,
)
from baserow.contrib.builder.workflow_actions.operations import (
    ListBuilderWorkflowActionsPageOperationType,
    ReadBuilderWorkflowActionOperationType,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(workflow_action_signals.workflow_action_created)
def workflow_action_created(
    sender,
    workflow_action: WorkflowAction,
    user: AbstractUser,
    before_id=None,
    **kwargs,
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow_action.page.builder.workspace_id,
            ReadBuilderWorkflowActionOperationType.type,
            BuilderWorkflowActionScopeType.type,
            workflow_action.id,
            {
                "type": "workflow_action_created",
                "page_id": workflow_action.page_id,
                "workflow_action": builder_workflow_action_type_registry.get_serializer(
                    workflow_action, BuilderWorkflowActionSerializer
                ).data,
                "before_id": before_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(workflow_action_signals.workflow_action_updated)
def workflow_action_updated(
    sender,
    workflow_action: WorkflowAction,
    user: AbstractUser,
    **kwargs,
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow_action.page.builder.workspace_id,
            ReadBuilderWorkflowActionOperationType.type,
            BuilderWorkflowActionScopeType.type,
            workflow_action.id,
            {
                "type": "workflow_action_updated",
                "page_id": workflow_action.page_id,
                "workflow_action": builder_workflow_action_type_registry.get_serializer(
                    workflow_action, BuilderWorkflowActionSerializer
                ).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(workflow_action_signals.workflow_action_deleted)
def workflow_action_deleted(
    sender,
    workflow_action_id: int,
    page: Page,
    user: AbstractUser,
    **kwargs,
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListBuilderWorkflowActionsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "workflow_action_deleted",
                "workflow_action_id": workflow_action_id,
                "page_id": page.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )
