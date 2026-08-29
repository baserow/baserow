from baserow.ws.tasks import broadcast_to_channel_group, broadcast_to_permitted_users

from .models import AgentChat


def get_agent_application_group_name(application_id: int) -> str:
    return f"agent_application-{application_id}"


def broadcast_chat_event(chat: AgentChat, event: dict) -> None:
    """
    Sends one streaming event of a running chat to everybody watching the
    application's page, so open history/chat views update live.
    """

    broadcast_to_channel_group.delay(
        get_agent_application_group_name(chat.agent.application_id),
        {
            "type": "agent_chat_event",
            "chat_id": chat.id,
            "event": event,
        },
    )


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


def broadcast_configuration_updated(application) -> None:
    """
    Signals that the application's trigger or tools changed, so open clients
    refetch them.
    """

    broadcast_to_channel_group.delay(
        get_agent_application_group_name(application.id),
        {
            "type": "agent_configuration_updated",
            "application_id": application.id,
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
