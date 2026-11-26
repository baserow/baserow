from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.contrib.agent.models import AgentChannel
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType

from .registries import agent_channel_type_registry
from .service import AgentChannelService


class AgentChannelActionType(ActionType):
    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        """
        :param agent_id: The id of the agent whose channels the action changes.
        :return: The application scope of the agent.
        """

        return ApplicationActionScopeType.value(agent_id)


class CreateAgentChannelActionType(AgentChannelActionType):
    """Adds a channel to an agent; not undoable, like the rest of its configuration."""

    type = "create_agent_channel"
    description = ActionTypeDescription(
        _("Create agent channel"),
        _(
            "Channel (%(channel_id)s) of type %(channel_type)s created in agent "
            "(%(agent_id)s)."
        ),
    )
    analytics_params = ["agent_id", "channel_type"]

    @dataclass
    class Params:
        agent_id: int
        channel_id: int
        channel_type: str

    @classmethod
    @transaction.atomic
    def do(
        cls, user: AbstractUser, agent_id: int, type_name: str, **values: Any
    ) -> AgentChannel:
        """
        :param user: The user adding the channel.
        :param agent_id: The id of the agent.
        :param type_name: The type of the channel.
        :param values: `enabled` and the values the type allows.
        :return: The created channel.
        """

        channel = AgentChannelService().create_channel(
            user, agent_id, type_name, **values
        )
        cls.register_action(
            user,
            cls.Params(agent_id, channel.id, type_name),
            cls.scope(agent_id),
            channel.agent.workspace,
        )
        return channel


class UpdateAgentChannelActionType(AgentChannelActionType):
    """Changes a channel; not undoable. Records field names, never values."""

    type = "update_agent_channel"
    description = ActionTypeDescription(
        _("Update agent channel"),
        _("Channel (%(channel_id)s) updated in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "channel_type", "changed_fields"]

    @dataclass
    class Params:
        agent_id: int
        channel_id: int
        channel_type: str
        changed_fields: list[str]

    @classmethod
    @transaction.atomic
    def do(
        cls, user: AbstractUser, agent_id: int, channel_id: int, **values: Any
    ) -> AgentChannel:
        """
        An update that changes nothing isn't audited.

        :param user: The user updating the channel.
        :param agent_id: The id of the agent the channel belongs to.
        :param channel_id: The id of the channel.
        :param values: `enabled` and the values its type allows.
        :return: The updated channel.
        """

        updated = AgentChannelService().update_channel(
            user, agent_id, channel_id, **values
        )
        channel = updated.channel
        if updated.changed_fields:
            cls.register_action(
                user,
                cls.Params(
                    agent_id,
                    channel.id,
                    agent_channel_type_registry.get_for_channel(channel).type,
                    updated.changed_fields,
                ),
                cls.scope(agent_id),
                channel.agent.workspace,
            )
        return channel


class DeleteAgentChannelActionType(AgentChannelActionType):
    """Trashes a channel; restored from the trash."""

    type = "delete_agent_channel"
    description = ActionTypeDescription(
        _("Delete agent channel"),
        _("Channel (%(channel_id)s) deleted in agent (%(agent_id)s)."),
    )
    analytics_params = ["agent_id", "channel_type"]

    @dataclass
    class Params:
        agent_id: int
        channel_id: int
        channel_type: str

    @classmethod
    @transaction.atomic
    def do(cls, user: AbstractUser, agent_id: int, channel_id: int) -> None:
        """
        :param user: The user deleting the channel.
        :param agent_id: The id of the agent the channel belongs to.
        :param channel_id: The id of the channel.
        """

        channel = AgentChannelService().delete_channel(user, agent_id, channel_id)
        cls.register_action(
            user,
            cls.Params(
                agent_id,
                channel.id,
                agent_channel_type_registry.get_for_channel(channel).type,
            ),
            cls.scope(agent_id),
            channel.agent.workspace,
        )
