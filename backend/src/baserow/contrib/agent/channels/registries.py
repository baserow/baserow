from typing import Any

from baserow.contrib.agent.models import AgentChannel
from baserow.core.models import Workspace
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

from .exceptions import AgentChannelTypeNotAvailable


class AgentChannelType(
    ModelInstanceMixin[AgentChannel], CustomFieldsInstanceMixin, Instance
):
    """One kind of place where people talk to an agent."""

    def is_deactivated(self, workspace: Workspace) -> bool:
        """
        :param workspace: The workspace of the channel's agent.
        :return: Whether the workspace's licence locks the type.
        """

        return False

    def prepare_values(self, values: dict[str, Any]) -> dict[str, Any]:
        """
        :param values: The type's accepted request values.
        :return: The values to store on its model.
        """

        return values

    def get_name(self, channel: AgentChannel) -> str:
        """
        :param channel: A channel of this type.
        :return: The name the trash and the audit log show for it.
        """

        return self.type


class AgentChannelTypeRegistry(
    ModelRegistryMixin[AgentChannel, AgentChannelType],
    Registry[AgentChannelType],
    CustomFieldsRegistryMixin[AgentChannel],
):
    name = "agent_channel"
    does_not_exist_exception_class = AgentChannelTypeNotAvailable

    def get_for_channel(self, channel: AgentChannel) -> AgentChannelType:
        """
        :param channel: A channel, of its type or not.
        :raises AgentChannelTypeNotAvailable: When its type isn't registered.
        :return: The type of the channel.
        """

        return self.get_by_model(channel.specific_class)


agent_channel_type_registry = AgentChannelTypeRegistry()
