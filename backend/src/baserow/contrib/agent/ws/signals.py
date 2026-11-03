from functools import partial
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.dispatch import receiver

from rest_framework.fields import DateTimeField

from baserow.contrib.agent.models import AgentConversation
from baserow.contrib.agent.signals import (
    agent_conversation_deleted,
    agent_conversation_renamed,
    agent_conversation_updated,
)
from baserow.contrib.agent.ws.tasks import broadcast_run_as_updates
from baserow.core.agents.signals import agent_created, agent_deleted, agent_updated
from baserow.core.models import Agent
from baserow.core.trash.signals import permanently_deleted
from baserow.ws.tasks import broadcast_to_users


@receiver(agent_created)
@receiver(agent_deleted)
def run_as_identity_changed(sender, agent: Agent, **kwargs) -> None:
    """Refresh application-scoped identity state after creation, restore or trash."""

    transaction.on_commit(
        partial(broadcast_run_as_updates.delay, agent.workspace_id, agent.id),
        using=DEFAULT_DB_ALIAS,
    )


@receiver(agent_updated)
def run_as_identity_updated(sender, agent: Agent, updated_fields=(), **kwargs) -> None:
    """Role and team changes do not alter identity names or availability."""

    if "name" in updated_fields:
        run_as_identity_changed(sender, agent)


@receiver(permanently_deleted)
def run_as_identity_permanently_deleted(
    sender, trash_item, trash_item_id: int, **kwargs
) -> None:
    """Refresh references after an identity is permanently removed from trash."""

    if isinstance(trash_item, Agent):
        transaction.on_commit(
            partial(
                broadcast_run_as_updates.delay, trash_item.workspace_id, trash_item_id
            ),
            using=DEFAULT_DB_ALIAS,
        )


def _notify_owner(
    conversation: AgentConversation,
    user: AbstractUser | None,
    event_type: str,
    **values: str | None,
) -> None:
    """Send an event about the conversation to its owner's other sessions only."""

    payload = {
        "type": event_type,
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        **values,
    }
    owner_id = conversation.owner_user_id
    web_socket_id = getattr(user, "web_socket_id", None)
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [owner_id], payload, ignore_web_socket_id=web_socket_id
        )
    )


@receiver(agent_conversation_updated)
def conversation_updated(
    sender,
    conversation: AgentConversation,
    user: AbstractUser | None,
    run_id: UUID | None = None,
    **kwargs,
):
    """Tell the owner's sessions which run is replying, without message content."""

    _notify_owner(
        conversation,
        user,
        "agent_conversation_updated",
        run_id=str(run_id) if run_id else None,
        updated_on=DateTimeField().to_representation(conversation.updated_on),
    )


@receiver(agent_conversation_renamed)
def conversation_renamed(
    sender, conversation: AgentConversation, user: AbstractUser, **kwargs
):
    _notify_owner(
        conversation, user, "agent_conversation_renamed", title=conversation.title
    )


@receiver(agent_conversation_deleted)
def conversation_deleted(
    sender, conversation: AgentConversation, user: AbstractUser, **kwargs
):
    _notify_owner(conversation, user, "agent_conversation_deleted")
