from baserow.core.agents.operations import DeleteAgentOperationType
from baserow.core.agents.signals import agent_created
from baserow.core.models import Agent
from baserow.core.trash.registries import TrashableItemType


class AgentTrashableItemType(TrashableItemType):
    type = "agent"
    model_class = Agent

    def get_parent(self, trashed_item):
        return trashed_item.workspace

    def get_name(self, trashed_item):
        return trashed_item.name

    def restore(self, trashed_item, trash_entry):
        super().restore(trashed_item, trash_entry)
        agent_created.send(self, user=None, agent=trashed_item)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        trashed_item.delete()

    def get_restore_operation_type(self):
        return DeleteAgentOperationType.type

    def get_restore_operation_context(self, trash_entry, trashed_item):
        return trashed_item.workspace
