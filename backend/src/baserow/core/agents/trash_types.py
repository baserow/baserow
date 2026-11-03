from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.operations import DeleteAgentOperationType
from baserow.core.agents.signals import agent_created
from baserow.core.exceptions import TrashItemDoesNotExist
from baserow.core.models import UserProfile
from baserow.core.trash.registries import TrashableItemType
from baserow.core.user.identity import is_agent_user


class AgentTrashableItemType(TrashableItemType):
    type = "agent"
    model_class = UserProfile

    def lookup_trashed_item(self, trashed_entry, trash_item_lookup_cache=None):
        profile = super().lookup_trashed_item(trashed_entry, trash_item_lookup_cache)
        if not is_agent_user(profile.user):
            raise TrashItemDoesNotExist()
        return profile

    def trash(self, item_to_trash, requesting_user, trash_entry):
        if not is_agent_user(item_to_trash.user):
            raise TrashItemDoesNotExist()
        super().trash(item_to_trash, requesting_user, trash_entry)

    def get_parent(self, trashed_item):
        return AgentHandler.get_workspace(trashed_item.user)

    def get_name(self, trashed_item):
        return trashed_item.user.first_name

    def restore(self, trashed_item, trash_entry):
        super().restore(trashed_item, trash_entry)
        agent_created.send(self, user=None, agent=trashed_item.user)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        if not is_agent_user(trashed_item.user):
            raise TrashItemDoesNotExist()
        trashed_item.user.delete()

    def get_restore_operation_type(self):
        return DeleteAgentOperationType.type

    def get_restore_operation_context(self, trash_entry, trashed_item):
        return AgentHandler.get_workspace(trashed_item.user)
