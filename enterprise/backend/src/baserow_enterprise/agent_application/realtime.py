from django.core.exceptions import SynchronousOnlyOperation

from loguru import logger

from baserow.ws.tasks import broadcast_to_channel_group, broadcast_to_permitted_users

from .models import AgentChat


def get_agent_application_group_name(application_id: int) -> str:
    return f"agent_application-{application_id}"


def get_public_chat_group_name(chat_uuid) -> str:
    return f"public-agent-chat-{chat_uuid}"


# The streaming event types an anonymous visitor of the public web chat
# receives, and the keys kept of each. Everything else (reasoning, tool calls
# and results, approvals, status texts, system messages) stays internal. See
# the exposure contract in `channels/web.py`.
PUBLIC_CHAT_EVENT_KEYS = {
    "ai/started": ("message_id",),
    "ai/answer_chunk": ("content",),
    "ai/message": ("id", "content"),
    "ai/cancelled": ("message_id",),
    # The error text may name tools or data; the visitor only learns it failed.
    "ai/error": (),
}


def public_chat_event(event: dict) -> dict | None:
    """
    Reduces an internal chat event to what the public page may see, or None
    when the event must not leave the workspace.
    """

    keys = PUBLIC_CHAT_EVENT_KEYS.get(event.get("type"))
    if keys is None:
        return None
    return {"type": event["type"], **{key: event.get(key) for key in keys}}


def _public_channel_type(chat: AgentChat):
    """
    The channel type when the chat belongs to a public web chat, else None.
    Broadcasts also happen inside the async runner, where a lazy load of the
    channel row is forbidden, so the channel must already be on the instance
    (the run task selects it) or is loaded through a thread-safe call.
    """

    if chat.channel_id is None:
        return None
    from .channels.registries import agent_chat_channel_type_registry
    from .channels.web import WebAgentChatChannelType

    channel_field = AgentChat._meta.get_field("channel")
    if not channel_field.is_cached(chat):
        try:
            chat.channel  # noqa: B018
        except SynchronousOnlyOperation:
            logger.warning(
                "Chat {} reached a broadcast from async code without its channel "
                "preloaded; the public page misses this update.",
                chat.id,
            )
            return None
    channel_type = agent_chat_channel_type_registry.get(chat.channel.type)
    return channel_type if isinstance(channel_type, WebAgentChatChannelType) else None


def broadcast_public_chat_event(chat: AgentChat, event: dict) -> None:
    if _public_channel_type(chat) is None:
        return
    public_event = public_chat_event(event)
    if public_event is None:
        return
    broadcast_to_channel_group.delay(
        get_public_chat_group_name(chat.uuid),
        {"type": "public_agent_chat_event", "event": public_event},
    )


def broadcast_public_chat_status(chat: AgentChat) -> None:
    if _public_channel_type(chat) is None:
        return
    from .channels.web import public_chat_status

    broadcast_to_channel_group.delay(
        get_public_chat_group_name(chat.uuid),
        {
            "type": "public_agent_chat_status",
            "status": public_chat_status(chat.status),
        },
    )


def broadcast_chat_event(chat: AgentChat, event: dict) -> None:
    """
    Sends one streaming event of a running chat to everybody watching the
    application's page, so open history/chat views update live. Public web
    chat conversations also get the public-safe subset of the event.
    """

    broadcast_to_channel_group.delay(
        get_agent_application_group_name(chat.agent.application_id),
        {
            "type": "agent_chat_event",
            "chat_id": chat.id,
            "event": event,
        },
    )
    broadcast_public_chat_event(chat, event)


def broadcast_agent_definition_updated(agent) -> None:
    """
    Lets open configuration panels live-update when the agent reconfigures
    itself from a conversation or another user edits it.
    """

    from baserow_enterprise.api.agent_application.serializers import (
        AgentDefinitionSerializer,
    )

    broadcast_to_channel_group.delay(
        get_agent_application_group_name(agent.application_id),
        {
            "type": "agent_definition_updated",
            "agent": AgentDefinitionSerializer(agent).data,
        },
    )


def broadcast_chat_deleted(application_id: int, chat_id: int) -> None:
    broadcast_to_channel_group.delay(
        get_agent_application_group_name(application_id),
        {
            "type": "agent_chat_deleted",
            "chat_id": chat_id,
        },
    )


def broadcast_pending_approvals_updated(application) -> None:
    """
    Notifies every user that can see the agent's conversations — anywhere in
    the workspace, not just on the agent page — that the number of tool calls
    waiting for approval changed, so sidebar and header indicators update.
    """

    from .handler import AgentChatHandler
    from .operations import ReadAgentChatOperationType

    count = AgentChatHandler().get_pending_approvals_count(application)
    broadcast_to_permitted_users.delay(
        application.workspace_id,
        ReadAgentChatOperationType.type,
        "application",
        application.id,
        {
            "type": "agent_pending_approvals_updated",
            "application_id": application.id,
            "count": count,
        },
    )


def broadcast_chat_updated(chat: AgentChat) -> None:
    """
    Sends the chat's new state (status, title, token usage) so conversation
    lists stay up to date.
    """

    from baserow_enterprise.api.agent_application.serializers import (
        AgentChatSerializer,
    )

    broadcast_to_channel_group.delay(
        get_agent_application_group_name(chat.agent.application_id),
        {
            "type": "agent_chat_updated",
            "chat": AgentChatSerializer(chat).data,
        },
    )
    broadcast_public_chat_status(chat)
