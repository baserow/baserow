from django.contrib.auth.models import AbstractUser

from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from .models import AgentApplication, AgentConversation
from .operations import RestoreAgentConversationOperationType
from .signals import agent_conversation_activity


class AgentConversationTrashableItemType(TrashableItemType):
    """A conversation only its owner sees and restores in the trash."""

    type = "agent_conversation"
    model_class = AgentConversation

    def get_parent(self, trashed_item: AgentConversation) -> AgentApplication:
        return trashed_item.agent

    def get_name(self, trashed_item: AgentConversation) -> str:
        return trashed_item.title

    def get_owner(self, trashed_item: AgentConversation) -> AbstractUser:
        return trashed_item.owner_user

    def permanently_delete_item(
        self,
        trashed_item: AgentConversation,
        trash_item_lookup_cache: dict | None = None,
    ) -> None:
        trashed_item.delete()

    def restore(self, trashed_item: AgentConversation, trash_entry: TrashEntry) -> None:
        super().restore(trashed_item, trash_entry)
        agent_conversation_activity.send(self, conversation=trashed_item, user=None)

    def get_restore_operation_type(self) -> str:
        return RestoreAgentConversationOperationType.type

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: AgentConversation
    ) -> AgentApplication:
        return trashed_item.agent
