from django.db import transaction
from django.dispatch import receiver

from baserow.ws.tasks import broadcast_to_channel_group

from ..realtime import (
    broadcast_agent_definition_updated,
    get_agent_application_group_name,
)
from ..signals import (
    agent_chat_channel_created,
    agent_chat_channel_deleted,
    agent_chat_channel_updated,
    agent_definition_updated,
    agent_tool_created,
    agent_tool_deleted,
    agent_tool_updated,
    agent_trigger_created,
    agent_trigger_deleted,
    agent_trigger_updated,
)


@receiver(agent_definition_updated)
def agent_definition_updated_receiver(sender, agent, user=None, **kwargs):
    broadcast_agent_definition_updated(agent)


def _broadcast(application_id: int, payload: dict, user) -> None:
    """
    Sent once the change is committed, and not back to the session that made
    it: that session already applied the change itself. An undo clears the
    user's web socket id, so the undoing session does receive its own events.
    """

    payload = {**payload, "application_id": application_id}
    transaction.on_commit(
        lambda: broadcast_to_channel_group.delay(
            get_agent_application_group_name(application_id),
            payload,
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(agent_trigger_created)
def agent_trigger_created_receiver(sender, trigger, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_trigger

    _broadcast(
        trigger.application_id,
        {"type": "agent_trigger_created", "trigger": _serialize_trigger(trigger)},
        user,
    )


@receiver(agent_trigger_updated)
def agent_trigger_updated_receiver(sender, trigger, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_trigger

    _broadcast(
        trigger.application_id,
        {"type": "agent_trigger_updated", "trigger": _serialize_trigger(trigger)},
        user,
    )


@receiver(agent_trigger_deleted)
def agent_trigger_deleted_receiver(
    sender, trigger_id, application, user=None, **kwargs
):
    _broadcast(
        application.id,
        {"type": "agent_trigger_deleted", "trigger_id": trigger_id},
        user,
    )


@receiver(agent_tool_created)
def agent_tool_created_receiver(sender, tool, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_tool

    _broadcast(
        tool.agent.application_id,
        {"type": "agent_tool_created", "tool": _serialize_tool(tool)},
        user,
    )


@receiver(agent_tool_updated)
def agent_tool_updated_receiver(sender, tool, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_tool

    _broadcast(
        tool.agent.application_id,
        {"type": "agent_tool_updated", "tool": _serialize_tool(tool)},
        user,
    )


@receiver(agent_tool_deleted)
def agent_tool_deleted_receiver(sender, tool_id, application, user=None, **kwargs):
    _broadcast(application.id, {"type": "agent_tool_deleted", "tool_id": tool_id}, user)


@receiver(agent_chat_channel_created)
def agent_chat_channel_created_receiver(sender, channel, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_channel

    _broadcast(
        channel.application_id,
        {
            "type": "agent_chat_channel_created",
            "channel": _serialize_channel(channel),
        },
        user,
    )


@receiver(agent_chat_channel_updated)
def agent_chat_channel_updated_receiver(sender, channel, user=None, **kwargs):
    from baserow_enterprise.api.agent_application.views import _serialize_channel

    _broadcast(
        channel.application_id,
        {
            "type": "agent_chat_channel_updated",
            "channel": _serialize_channel(channel),
        },
        user,
    )


@receiver(agent_chat_channel_deleted)
def agent_chat_channel_deleted_receiver(
    sender, channel_id, application, user=None, **kwargs
):
    _broadcast(
        application.id,
        {"type": "agent_chat_channel_deleted", "channel_id": channel_id},
        user,
    )
