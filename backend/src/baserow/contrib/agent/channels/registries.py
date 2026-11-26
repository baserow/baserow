from typing import Any

from baserow.contrib.agent.models import AgentApplication, AgentChannel
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
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

    def export_serialized(
        self, channel: AgentChannel, import_export_config: ImportExportConfig
    ) -> dict[str, Any]:
        """
        :param channel: A channel of this type.
        :param import_export_config: How the agent is exported.
        :return: What a copy of the channel keeps, never its address.
        """

        return {"id": channel.id, "type": self.type}

    def import_serialized(
        self,
        agent: AgentApplication,
        serialized: dict[str, Any],
        import_export_config: ImportExportConfig,
        **values: Any,
    ) -> AgentChannel:
        """
        Create the copy switched off, since it would answer anyone who reaches it.

        :param agent: The agent the channel is copied into.
        :param serialized: The channel from ``export_serialized``.
        :param import_export_config: How the agent is imported.
        :param values: The type's own values for the copy.
        :return: The copied channel.
        """

        return self.model_class.objects.create(agent=agent, enabled=False, **values)


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
