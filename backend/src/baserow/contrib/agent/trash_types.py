from django.contrib.auth.models import AbstractUser

from baserow.core.models import TrashEntry
from baserow.core.signals import application_pending_count_updated
from baserow.core.trash.registries import TrashableItemType

from .handler import AgentHandler
from .models import AgentApplication, AgentConversation
from .operations import RestoreAgentConversationOperationType
from .signals import agent_conversation_activity


class AgentConversationTrashableItemType(TrashableItemType):
    """
    A conversation only its owner sees and restores in the trash; a shared one has
    no owner, so every reader sees it there but, as for trashing it, only a user
    who may update the Agent restores it.
    """

    type = "agent_conversation"
    model_class = AgentConversation

    def get_parent(self, trashed_item: AgentConversation) -> AgentApplication:
        return trashed_item.agent

    def get_name(self, trashed_item: AgentConversation) -> str:
        return trashed_item.title

    def get_owner(self, trashed_item: AgentConversation) -> AbstractUser | None:
        """
        :param trashed_item: The trashed conversation.
        :return: Its owner, whose trash alone lists it, or None for a shared one,
            which every trash reader sees.
        """

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
        if AgentHandler().conversation_has_pending_approvals(trashed_item.id):
            application_pending_count_updated.send(
                self,
                application=trashed_item.agent,
                user_ids=trashed_item.pending_count_user_ids,
            )

    def get_restore_operation_type(self) -> str:
        return RestoreAgentConversationOperationType.type

    def get_restore_operation_types(self, trashed_item: AgentConversation) -> list[str]:
        """
        A shared conversation also needs builders, as trashing it did.

        :param trashed_item: The trashed conversation.
        :return: The operations a user needs on the Agent to restore it.
        """

        return [
            self.get_restore_operation_type(),
            *AgentHandler().get_shared_change_operations(trashed_item),
        ]

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: AgentConversation
    ) -> AgentApplication:
        return trashed_item.agent
