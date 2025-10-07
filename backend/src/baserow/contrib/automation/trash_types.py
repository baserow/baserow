from baserow.contrib.automation.models import Automation
from baserow.core.models import TrashEntry, Workspace
from baserow.core.operations import RestoreApplicationOperationType
from baserow.core.signals import application_created
from baserow.core.trash.registries import TrashableItemType


class AutomationTrashableItemType(TrashableItemType):
    type = "automation"
    model_class = Automation

    def get_parent(self, trashed_item: Automation) -> Workspace:
        return trashed_item.workspace

    def get_name(self, trashed_item: Automation) -> str:
        return trashed_item.name

    def trash(
        self,
        item_to_trash: Automation,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        """
        When an Automation application is trashed, ensure that all
        related published Automations are deleted.
        """

        Automation.objects.filter(published_from__automation=item_to_trash).delete()

        super().trash(item_to_trash, requesting_user, trash_entry)

    def restore(
        self,
        trashed_item: Automation,
        trash_entry: TrashEntry,
    ):
        super().restore(trashed_item, trash_entry)
        application_created.send(self, application=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: Automation, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreApplicationOperationType.type
