from functools import partial
from typing import Any
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.dispatch import receiver

from baserow.contrib.agent.action_tools.signals import (
    agent_action_created,
    agent_action_deleted,
    agent_action_updated,
)
from baserow.contrib.agent.api.action_tools.serializers import AgentActionSerializer
from baserow.contrib.agent.api.serializers import AgentConversationSerializer
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentAction, AgentConversation
from baserow.contrib.agent.operations import (
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
)
from baserow.contrib.agent.signals import (
    agent_conversation_activity,
    agent_conversation_deleted,
    agent_conversation_updated,
)
from baserow.contrib.agent.ws.tasks import broadcast_run_as_updates
from baserow.core.agents.signals import agent_created, agent_deleted, agent_updated
from baserow.core.models import Agent
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.core.trash.signals import permanently_deleted
from baserow.ws.tasks import broadcast_to_permitted_users, broadcast_to_users


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


def _notify_readers(
    conversation: AgentConversation,
    user: AbstractUser | None,
    event_type: str,
    /,
    **data: object,
) -> None:
    """
    Send an event to the sessions that see the conversation, except the acting one:
    the owner's for a private conversation, every reader's of the Agent for a
    shared one.

    :param conversation: The conversation the event is about.
    :param user: The acting user, whose own session already knows, or None.
    :param event_type: The realtime event type.
    :param data: The rest of the payload.
    """

    payload = {
        "type": event_type,
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        **data,
    }
    web_socket_id = getattr(user, "web_socket_id", None)
    if not conversation.is_shared:
        send = partial(
            broadcast_to_users.delay,
            [conversation.owner_user_id],
            payload,
            ignore_web_socket_id=web_socket_id,
        )
    else:
        agent = conversation.agent
        send = partial(
            broadcast_to_permitted_users.delay,
            agent.workspace_id,
            ReadAgentConversationsOperationType.type,
            ApplicationObjectScopeType.type,
            agent.id,
            payload,
            ignore_web_socket_id=web_socket_id,
        )
    transaction.on_commit(send)


def _serialize_listed(
    conversation: AgentConversation, conversation_runs: dict[int, UUID | str]
) -> dict:
    """Serialize the conversation as the conversation list shows it."""

    context = {
        "conversation_runs": conversation_runs,
        "conversation_pending_approvals": (
            AgentHandler().get_conversation_pending_approval_counts([conversation.id])
        ),
    }
    return AgentConversationSerializer(conversation, context=context).data


@receiver(agent_conversation_activity)
def conversation_activity(
    sender,
    conversation: AgentConversation,
    user: AbstractUser | None,
    run_id: UUID | None = None,
    **kwargs,
) -> None:
    """Send the conversation and the run replying in it, without message content."""

    # A deleted conversation is already gone from every list.
    if conversation.trashed:
        return
    _notify_readers(
        conversation,
        user,
        "agent_conversation_activity",
        conversation=_serialize_listed(
            conversation, {conversation.id: str(run_id)} if run_id else {}
        ),
    )


@receiver(agent_conversation_updated)
def conversation_updated(
    sender,
    conversation: AgentConversation,
    user: AbstractUser,
    values: dict[str, str | bool],
    **kwargs,
) -> None:
    """
    Send the changed values, and the whole conversation for the lists that have not
    loaded it, so every reader's list shows the change without a re-read.
    """

    _notify_readers(
        conversation,
        user,
        "agent_conversation_updated",
        values=values,
        conversation=_serialize_listed(
            conversation, AgentHandler().get_conversation_runs([conversation.id])
        ),
    )


@receiver(agent_conversation_deleted)
def conversation_deleted(
    sender, conversation: AgentConversation, user: AbstractUser, **kwargs
) -> None:
    """Remove the conversation from every reader's other lists."""

    _notify_readers(conversation, user, "agent_conversation_deleted")


def _notify_action_configuration(
    instance: AgentAction, user: AbstractUser | None, event_type: str, **values: Any
) -> None:
    """
    Tell the users who may read the Agent's configuration, and nobody else: an
    action holds its template's content.

    :param instance: The action that changed.
    :param user: The user who changed it, whose own session isn't told.
    :param event_type: The realtime event.
    :param values: What the event carries besides the Agent's id.
    """

    transaction.on_commit(
        partial(
            broadcast_to_permitted_users.delay,
            instance.agent.workspace_id,
            ReadAgentConfigurationOperationType.type,
            ApplicationObjectScopeType.type,
            instance.agent_id,
            {"type": event_type, "agent_id": instance.agent_id, **values},
            ignore_web_socket_id=getattr(user, "web_socket_id", None),
        )
    )


@receiver(agent_action_created)
def action_created(
    sender: Any, action: AgentAction, user: AbstractUser | None, **kwargs
) -> None:
    _notify_action_configuration(
        action, user, "agent_action_created", action=AgentActionSerializer(action).data
    )


@receiver(agent_action_updated)
def action_updated(
    sender: Any, action: AgentAction, user: AbstractUser | None, **kwargs
) -> None:
    _notify_action_configuration(
        action, user, "agent_action_updated", action=AgentActionSerializer(action).data
    )


@receiver(agent_action_deleted)
def action_deleted(
    sender: Any, action: AgentAction, user: AbstractUser | None, **kwargs
) -> None:
    _notify_action_configuration(
        action, user, "agent_action_deleted", action_id=action.id
    )
