from django.db import transaction

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.trash.registries import TrashableItemType

from .handler import AgentActionHandler
from .signals import agent_action_created


class AgentActionTrashableItemType(TrashableItemType):
    type = "agent_action"
    model_class = AgentAction

    def get_parent(self, trashed_item: AgentAction) -> AgentApplication:
        return trashed_item.agent

    def get_name(self, trashed_item: AgentAction) -> str:
        return trashed_item.name

    def trash(self, item_to_trash, requesting_user, trash_entry):
        super().trash(item_to_trash, requesting_user, trash_entry)
        self._set_service_trashed(item_to_trash, True)

    @transaction.atomic
    def restore(self, trashed_item, trash_entry):
        AgentApplication.objects.select_for_update().get(pk=trashed_item.agent_id)
        # A new action may have reused the old name while this one was trashed.
        # Keep both identities and allocate a fresh callable name to the restored one.
        trashed_item.name = AgentActionHandler().unique_name(
            trashed_item.agent, trashed_item.name, trashed_item.id
        )
        trashed_item.save(update_fields=["name"])
        super().restore(trashed_item, trash_entry)
        self._set_service_trashed(trashed_item, False)
        agent_action_created.send(self, action=trashed_item, user=None)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        trashed_item.delete()

    def get_restore_operation_type(self):
        return UpdateApplicationOperationType.type

    def get_restore_operation_context(self, trash_entry, trashed_item):
        return trashed_item.agent

    @staticmethod
    def _set_service_trashed(action, trashed):
        service = action.service
        service.trashed = trashed
        service.save(update_fields=["trashed"])
