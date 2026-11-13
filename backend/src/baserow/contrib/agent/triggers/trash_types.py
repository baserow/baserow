from django.contrib.auth.models import AbstractUser

from baserow.contrib.agent.models import AgentApplication, AgentTrigger
from baserow.core.models import TrashEntry
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.trash.registries import TrashableItemType

from .handler import AgentTriggerHandler


class AgentTriggerTrashableItemType(TrashableItemType):
    """A trigger is trashed with its service, so no event reaches it meanwhile."""

    type = "agent_trigger"
    model_class = AgentTrigger

    def get_parent(self, trashed_item: AgentTrigger) -> AgentApplication:
        """
        :param trashed_item: The trashed trigger.
        :return: The Agent the trigger belongs to.
        """

        return trashed_item.agent

    def get_name(self, trashed_item: AgentTrigger) -> str:
        """
        :param trashed_item: The trashed trigger.
        :return: The trigger's name, blank when it has none, which the trash shows
            as an unnamed trigger.
        """

        return trashed_item.name

    def trash(
        self,
        item_to_trash: AgentTrigger,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ) -> None:
        """
        Trash the trigger and its service.

        :param item_to_trash: The trigger to trash.
        :param requesting_user: The user trashing it.
        :param trash_entry: The trash entry of the trigger.
        """

        super().trash(item_to_trash, requesting_user, trash_entry)
        self._set_service_trashed(item_to_trash, True)

    def restore(self, trashed_item: AgentTrigger, trash_entry: TrashEntry) -> None:
        """
        Restore the trigger and its service, and arm it again from now.

        :param trashed_item: The trashed trigger.
        :param trash_entry: The trash entry of the trigger.
        """

        super().restore(trashed_item, trash_entry)
        self._set_service_trashed(trashed_item, False)
        AgentTriggerHandler().arm(trashed_item)

    def permanently_delete_item(
        self, trashed_item: AgentTrigger, trash_item_lookup_cache: dict | None = None
    ) -> None:
        """
        Delete the trigger, cancelling its queued replies: their conversations
        lose the trigger, so nothing would start them. Its ``post_delete``
        receiver deletes the service.

        :param trashed_item: The trashed trigger.
        :param trash_item_lookup_cache: Unused, a trigger has no trashed children.
        """

        AgentTriggerHandler().cancel_queued_replies(trashed_item)
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        """
        :return: The operation a user needs on the Agent to restore a trigger.
        """

        return UpdateApplicationOperationType.type

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: AgentTrigger
    ) -> AgentApplication:
        """
        :param trash_entry: The trash entry of the trigger.
        :param trashed_item: The trashed trigger.
        :return: The Agent the restore operation is checked on.
        """

        return trashed_item.agent

    @staticmethod
    def _set_service_trashed(trigger: AgentTrigger, trashed: bool) -> None:
        """
        Mirror the trigger's trashed state on its service, so the due and webhook
        lookups skip it without joining triggers.

        :param trigger: The trigger whose service to update.
        :param trashed: Whether the service is now trashed.
        """

        service = trigger.service
        service.trashed = trashed
        service.save(update_fields=["trashed"])
