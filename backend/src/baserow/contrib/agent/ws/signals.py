from functools import partial
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.dispatch import receiver

from rest_framework.fields import DateTimeField

from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.signals import agent_conversation_updated
from baserow.core.agents.signals import agent_created, agent_deleted, agent_updated
from baserow.core.models import Agent
from baserow.core.trash.signals import permanently_deleted
from baserow.ws.tasks import broadcast_to_permitted_users, broadcast_to_users


def _invalidate_run_as_options(workspace_id: int, identity_id: int) -> None:
    """Invalidate identity choices and affected selections after a committed change.

    :param workspace_id: The workspace whose available identities changed.
    :param identity_id: The changed identity, including a permanently deleted one.
    """

    applications = (
        AgentApplication.objects.using(DEFAULT_DB_ALIAS)
        .filter(workspace_id=workspace_id, workspace__trashed=False)
        .values_list("id", "run_as_subject_type", "run_as_subject_id")
    )
    for application_id, subject_type, subject_id in applications.iterator():
        # Application builders need these invalidations even when they cannot list
        # workspace identities. Never widen the audience of identity-management
        # payloads, which include roles and other unrelated details.
        broadcast_to_permitted_users.delay(
            workspace_id,
            ReadAgentConfigurationOperationType.type,
            "application",
            application_id,
            {
                "type": "agent_run_as_updated",
                "agent_id": application_id,
                "selected_identity_changed": (
                    subject_type == "core.Agent" and subject_id == identity_id
                ),
            },
        )


@receiver(agent_created)
@receiver(agent_updated)
@receiver(agent_deleted)
def run_as_identity_changed(sender, agent: Agent, **kwargs) -> None:
    """Refresh application-scoped identity state after creation, editing or trash."""

    transaction.on_commit(
        partial(_invalidate_run_as_options, agent.workspace_id, agent.id),
        using=DEFAULT_DB_ALIAS,
    )


@receiver(permanently_deleted)
def run_as_identity_permanently_deleted(
    sender, trash_item, trash_item_id: int, **kwargs
) -> None:
    """Refresh references after an identity is permanently removed from trash."""

    if isinstance(trash_item, Agent):
        transaction.on_commit(
            partial(_invalidate_run_as_options, trash_item.workspace_id, trash_item_id),
            using=DEFAULT_DB_ALIAS,
        )


@receiver(agent_conversation_updated)
def conversation_updated(
    sender,
    conversation: AgentConversation,
    user: AbstractUser | None,
    run_id: UUID | None = None,
    **kwargs,
):
    """Tell the owner's sessions which run is replying, without private content."""

    payload = {
        "type": "agent_conversation_updated",
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        "run_id": str(run_id) if run_id else None,
        "updated_on": DateTimeField().to_representation(conversation.updated_on),
    }
    owner_id = conversation.owner_user_id
    web_socket_id = getattr(user, "web_socket_id", None)
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [owner_id], payload, ignore_web_socket_id=web_socket_id
        )
    )
