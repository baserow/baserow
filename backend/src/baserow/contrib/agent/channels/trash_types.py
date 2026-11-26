from baserow.contrib.agent.models import AgentApplication, AgentChannel
from baserow.core.models import TrashEntry
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.trash.registries import TrashableItemType

from .registries import agent_channel_type_registry
from .service import WRITE_OPERATIONS


class AgentChannelTrashableItemType(TrashableItemType):
    """A trashed channel keeps its settings and can't be used until restored."""

    type = "agent_channel"
    model_class = AgentChannel

    def get_parent(self, trashed_item: AgentChannel) -> AgentApplication:
        return trashed_item.agent

    def get_name(self, trashed_item: AgentChannel) -> str:
        """
        :param trashed_item: The trashed channel.
        :return: The name its type gives it.
        """

        channel = trashed_item.specific
        return agent_channel_type_registry.get_by_model(channel).get_name(channel)

    def restore(self, trashed_item: AgentChannel, trash_entry: TrashEntry) -> None:
        super().restore(trashed_item, trash_entry)

    def permanently_delete_item(
        self, trashed_item: AgentChannel, trash_item_lookup_cache: dict | None = None
    ) -> None:
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return UpdateApplicationOperationType.type

    def get_restore_operation_types(self, trashed_item: AgentChannel) -> list[str]:
        return list(WRITE_OPERATIONS)

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: AgentChannel
    ) -> AgentApplication:
        return trashed_item.agent
