from typing import TYPE_CHECKING, Any, Optional

from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.operations import RestoreUserSourceOperationType
from baserow.core.user_sources.signals import (
    user_source_created,
    user_source_deleted,
)

if TYPE_CHECKING:
    from baserow.core.models import Application


class UserSourceTrashableItemType(TrashableItemType):
    type = "user_source"
    model_class = UserSource

    def get_parent(self, trashed_item: UserSource) -> "Application":
        return trashed_item.application

    def get_name(self, trashed_item: UserSource) -> str:
        # The application is already shown as the trash entry's parent (get_parent
        # returns it), so it isn't repeated here.
        return f"{trashed_item.name} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: UserSource,
        requesting_user,
        trash_entry: TrashEntry,
    ) -> None:
        application = item_to_trash.application
        super().trash(item_to_trash, requesting_user, trash_entry)
        user_source_deleted.send(
            self,
            user_source_id=item_to_trash.id,
            application=application,
            user=requesting_user,
        )

    def restore(self, trashed_item: UserSource, trash_entry: TrashEntry) -> None:
        super().restore(trashed_item, trash_entry)
        user_source_created.send(
            self,
            user_source=trashed_item,
            user=None,
            before_id=None,
        )

    def permanently_delete_item(
        self, trashed_item: UserSource, trash_item_lookup_cache: Optional[Any] = None
    ) -> None:
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreUserSourceOperationType.type
