from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.models import AgentChannel
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.types import AgentChannelUpdated
from baserow.core.operations import UpdateApplicationOperationType

from .exceptions import AgentChannelTypeNotAvailable
from .handler import AgentChannelHandler
from .registries import agent_channel_type_registry

WRITE_OPERATIONS = (
    UpdateApplicationOperationType.type,
    ReadAgentConfigurationOperationType.type,
)


class AgentChannelService:
    """Channel changes for a user allowed to make them on the channel's agent."""

    def __init__(self) -> None:
        self.handler = AgentChannelHandler()
        self.agent_service = AgentService()

    def list_channels(self, user: AbstractUser, agent_id: int) -> list[AgentChannel]:
        """
        :param user: The user listing the channels.
        :param agent_id: The id of the agent.
        :raises ApplicationDoesNotExist: When the agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not read its configuration.
        :return: The channels, oldest first.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.list_channels(agent)

    def get_channel(
        self, user: AbstractUser, agent_id: int, channel_id: int
    ) -> AgentChannel:
        """
        :param user: The user reading the channel.
        :param agent_id: The id of the agent the channel belongs to.
        :param channel_id: The id of the channel.
        :raises ApplicationDoesNotExist: When the agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not read its configuration.
        :raises AgentChannelDoesNotExist: When the agent has no such channel.
        :return: The channel of its type.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, ReadAgentConfigurationOperationType.type
        )
        return self.handler.get_channel(
            channel_id, base_queryset=AgentChannel.objects.filter(agent=agent)
        )

    @transaction.atomic
    def create_channel(
        self, user: AbstractUser, agent_id: int, type_name: str, **values: Any
    ) -> AgentChannel:
        """
        :param user: The user adding the channel.
        :param agent_id: The id of the agent.
        :param type_name: The type of the channel.
        :param values: `enabled` and the values the type allows.
        :raises ApplicationDoesNotExist: When the agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the agent or read
            its configuration.
        :raises AgentChannelTypeNotAvailable: When the type isn't registered or the
            workspace can't use it.
        :return: The created channel.
        """

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS
        )
        channel_type = agent_channel_type_registry.get(type_name)
        if channel_type.is_deactivated(agent.workspace):
            raise AgentChannelTypeNotAvailable(type_name)
        return self.handler.create_channel(agent, channel_type, **values)

    @transaction.atomic
    def update_channel(
        self, user: AbstractUser, agent_id: int, channel_id: int, **values: Any
    ) -> AgentChannelUpdated:
        """
        A channel whose type the workspace can't use may only be switched off.

        :param user: The user updating the channel.
        :param agent_id: The id of the agent the channel belongs to.
        :param channel_id: The id of the channel.
        :param values: `enabled` and the values its type allows.
        :raises ApplicationDoesNotExist: When the agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the agent or read
            its configuration.
        :raises AgentChannelDoesNotExist: When the agent has no such channel.
        :raises AgentChannelTypeNotAvailable: When it would change anything but
            switching off a channel whose type the workspace can't use.
        :return: The channel and the names of the fields that changed.
        """

        channel = self._get_authorized_channel(user, agent_id, channel_id)
        if any(
            name != "enabled" or value for name, value in values.items()
        ) and self.handler.is_type_locked(channel, channel.agent.workspace):
            raise AgentChannelTypeNotAvailable
        return self.handler.update_channel(channel, **values)

    @transaction.atomic
    def delete_channel(
        self, user: AbstractUser, agent_id: int, channel_id: int
    ) -> AgentChannel:
        """
        :param user: The user deleting the channel.
        :param agent_id: The id of the agent the channel belongs to.
        :param channel_id: The id of the channel.
        :raises ApplicationDoesNotExist: When the agent doesn't exist or is trashed.
        :raises PermissionException: When the user may not update the agent or read
            its configuration.
        :raises AgentChannelDoesNotExist: When the agent has no such channel.
        :return: The channel, now in the trash.
        """

        channel = self._get_authorized_channel(user, agent_id, channel_id)
        self.handler.delete_channel(user, channel)
        return channel

    def _get_authorized_channel(
        self, user: AbstractUser, agent_id: int, channel_id: int
    ) -> AgentChannel:
        """The channel, locked, for a user allowed to change it."""

        agent = self.agent_service.get_authorized_agent(
            user, agent_id, *WRITE_OPERATIONS
        )
        return self.handler.get_channel(
            channel_id,
            base_queryset=AgentChannel.objects.filter(agent=agent).select_for_update(
                of=("self",)
            ),
        )
