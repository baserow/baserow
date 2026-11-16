from baserow.contrib.automation.models import Automation
from baserow.core.models import TrashEntry
from baserow.core.trash.trash_types import ApplicationTrashableItemType


class AutomationTrashableItemType(ApplicationTrashableItemType):
    """
    Trashes an automation like any other application, and also deletes the
    automations published from it.

    Its trash entries are stored as `application` entries, so only `trash` runs
    here: restoring and permanently deleting them use the application type. The
    `automation` type stays registered for the entries stored before that.
    """

    type = "automation"
    model_class = Automation

    @property
    def entry_type(self) -> str:
        return ApplicationTrashableItemType.type

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
