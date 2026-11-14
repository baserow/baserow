from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.core.models import TrashEntry
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.registries import TrashableItemType

from .exceptions import AgentActionLimitReached
from .handler import AgentActionHandler
from .signals import agent_action_created


class AgentActionTrashableItemType(TrashableItemType):
    """An action is trashed with its service, so nothing can dispatch it meanwhile."""

    type = "agent_action"
    model_class = AgentAction

    def get_parent(self, trashed_item: AgentAction) -> AgentApplication:
        """
        :param trashed_item: The trashed action.
        :return: The Agent the action belongs to.
        """

        return trashed_item.agent

    def get_name(self, trashed_item: AgentAction) -> str:
        """
        :param trashed_item: The trashed action.
        :return: The name the model called it by.
        """

        return trashed_item.name

    def trash(
        self,
        item_to_trash: AgentAction,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ) -> None:
        """
        Trash the action and its service.

        :param item_to_trash: The action to trash.
        :param requesting_user: The user trashing it.
        :param trash_entry: The trash entry of the action.
        """

        super().trash(item_to_trash, requesting_user, trash_entry)
        self._set_service_trashed(item_to_trash, True)

    @transaction.atomic
    def restore(self, trashed_item: AgentAction, trash_entry: TrashEntry) -> None:
        """
        Restore the action and its service. A new action may have taken its name
        meanwhile: both stay, and the restored one gets the next free name.

        :param trashed_item: The trashed action.
        :param trash_entry: The trash entry of the action.
        :raises TrashItemRestorationDisallowed: When the Agent can't have one more
            action.
        """

        agent = AgentApplication.objects.select_for_update().get(
            pk=trashed_item.agent_id
        )
        handler = AgentActionHandler()
        try:
            handler.check_limit(agent)
        except AgentActionLimitReached as exc:
            raise TrashItemRestorationDisallowed(str(exc)) from exc
        trashed_item.name = handler.unique_name(
            agent, trashed_item.name, trashed_item.id
        )
        trashed_item.save(update_fields=["name"])
        super().restore(trashed_item, trash_entry)
        self._set_service_trashed(trashed_item, False)
        agent_action_created.send(self, action=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AgentAction, trash_item_lookup_cache: dict | None = None
    ) -> None:
        """
        :param trashed_item: The action to delete, with the service it owns.
        :param trash_item_lookup_cache: Unused.
        """

        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        """
        :return: The operation a user needs on the Agent to restore its action.
        """

        return UpdateApplicationOperationType.type

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: AgentAction
    ) -> AgentApplication:
        """
        :param trash_entry: The trash entry of the action.
        :param trashed_item: The trashed action.
        :return: The Agent the restore operation is checked on.
        """

        return trashed_item.agent

    @staticmethod
    def _set_service_trashed(action: AgentAction, trashed: bool) -> None:
        service = action.service
        service.trashed = trashed
        service.save(update_fields=["trashed"])
