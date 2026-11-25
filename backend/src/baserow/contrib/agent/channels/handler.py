from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.agent.models import AgentApplication, AgentChannel
from baserow.contrib.agent.types import AgentChannelUpdated
from baserow.core.db import specific_iterator
from baserow.core.models import Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import extract_allowed

from .exceptions import AgentChannelDoesNotExist
from .registries import AgentChannelType, agent_channel_type_registry


class AgentChannelHandler:
    """The channels of agents, without permission checks."""

    def get_channel(
        self, channel_id: int, base_queryset: QuerySet[AgentChannel] | None = None
    ) -> AgentChannel:
        """
        :param channel_id: The id of the channel.
        :param base_queryset: The queryset to look the channel up in, to add a lock
            or a filter. Defaults to the channels that aren't trashed.
        :raises AgentChannelDoesNotExist: When the channel doesn't exist or is
            trashed.
        :return: The channel of its type, with its agent and workspace.
        """

        queryset = (
            base_queryset if base_queryset is not None else AgentChannel.objects.all()
        )
        channels = specific_iterator(
            queryset.select_related("agent__workspace").filter(id=channel_id)
        )
        if not channels:
            raise AgentChannelDoesNotExist
        return channels[0]

    def list_channels(self, agent: AgentApplication) -> list[AgentChannel]:
        """
        :param agent: The agent the channels belong to.
        :return: The channels that aren't trashed, each of its type, oldest first,
            loaded with one query per type.
        """

        return specific_iterator(AgentChannel.objects.filter(agent=agent))

    def is_type_locked(self, channel: AgentChannel, workspace: Workspace) -> bool:
        """
        :param channel: The channel, of any type.
        :param workspace: The workspace of the channel's agent.
        :raises AgentChannelTypeNotAvailable: When its type isn't registered.
        :return: Whether the workspace can't use the channel's type.
        """

        return agent_channel_type_registry.get_for_channel(channel).is_deactivated(
            workspace
        )

    def create_channel(
        self, agent: AgentApplication, channel_type: AgentChannelType, **values: Any
    ) -> AgentChannel:
        """
        :param agent: The agent the channel belongs to.
        :param channel_type: The type of the channel.
        :param values: `enabled` and the values the type allows.
        :return: The created channel.
        """

        return channel_type.model_class.objects.create(
            agent=agent, **self._prepare_values(channel_type, values)
        )

    def update_channel(
        self, channel: AgentChannel, **values: Any
    ) -> AgentChannelUpdated:
        """
        Write only the values that differ from the saved ones.

        :param channel: The channel of its type.
        :param values: `enabled` and the values its type allows.
        :return: The channel and the names of the fields that changed.
        """

        channel_type = agent_channel_type_registry.get_for_channel(channel)
        prepared = self._prepare_values(channel_type, values)
        changed_fields = [
            name for name, value in prepared.items() if getattr(channel, name) != value
        ]
        for name in changed_fields:
            setattr(channel, name, prepared[name])
        if changed_fields:
            channel.save(update_fields=[*changed_fields, "updated_on"])
        return AgentChannelUpdated(channel, changed_fields)

    def delete_channel(self, user: AbstractUser, channel: AgentChannel) -> None:
        """
        :param user: The user deleting the channel.
        :param channel: The channel to move to the trash, with its agent.
        """

        agent = channel.agent
        TrashHandler.trash(user, agent.workspace, agent, channel)

    def _prepare_values(
        self, channel_type: AgentChannelType, values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        :param channel_type: The type of the channel.
        :param values: The requested values.
        :return: `enabled` and the type's allowed values, ready to store.
        """

        return extract_allowed(values, ["enabled"]) | channel_type.prepare_values(
            extract_allowed(values, channel_type.allowed_fields)
        )
