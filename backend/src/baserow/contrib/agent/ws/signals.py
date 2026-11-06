from functools import partial
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.dispatch import receiver

from rest_framework.fields import DateTimeField

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentConversation
from baserow.contrib.agent.signals import (
    agent_conversation_activity,
    agent_conversation_deleted,
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
    **data: object,
) -> None:
    """Send an event to the conversation owner's sessions, except the acting one."""

    payload = {
        "type": event_type,
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        **data,
    }
    owner_id = conversation.owner_user_id
    web_socket_id = getattr(user, "web_socket_id", None)
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [owner_id], payload, ignore_web_socket_id=web_socket_id
        )
    )


@receiver(agent_conversation_activity)
def conversation_activity(
    sender,
    conversation: AgentConversation,
    user: AbstractUser | None,
    run_id: UUID | None = None,
    **kwargs,
) -> None:
    """Tell the owner's sessions which run replies and how many held calls wait."""

    # A deleted conversation is already gone from every list.
    if conversation.trashed:
        return
    _notify_owner(
        conversation,
        user,
        "agent_conversation_activity",
        run_id=str(run_id) if run_id else None,
        updated_on=DateTimeField().to_representation(conversation.updated_on),
        pending_approval_count=AgentHandler().count_pending_approvals(conversation),
    )


@receiver(agent_conversation_updated)
def conversation_updated(
    sender,
    conversation: AgentConversation,
    user: AbstractUser,
    values: dict[str, str],
    **kwargs,
) -> None:
    """Send the changed values, so the owner's lists show them without a re-read."""

    _notify_owner(conversation, user, "agent_conversation_updated", values=values)


@receiver(agent_conversation_deleted)
def conversation_deleted(
    sender, conversation: AgentConversation, user: AbstractUser, **kwargs
) -> None:
    """Remove the conversation from the owner's other lists."""

    _notify_owner(conversation, user, "agent_conversation_deleted")
