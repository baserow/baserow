from typing import Any, Optional

from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.operations import RestorePageOperationType
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from .signals import page_created, page_deleted


class PageTrashableItemType(TrashableItemType):
    type = "builder_page"
    model_class = Page

    def get_parent(self, trashed_item: Page) -> Optional[Any]:
        return trashed_item.builder

    def get_name(self, trashed_item: Page) -> str:
        page_name = (
            trashed_item.name if not trashed_item.shared else trashed_item.builder.name
        )
        return f"{page_name} ({trashed_item.id})"

    def trash(self, item_to_trash: Page, requesting_user, trash_entry: TrashEntry):
        super().trash(item_to_trash, requesting_user, trash_entry)
        page_deleted.send(
            self,
            builder=item_to_trash.builder,
            page_id=item_to_trash.id,
            user=requesting_user,
        )

    def restore(self, trashed_item: Page, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)
        PageHandler().invalidate_page_cache(trashed_item)
        page_created.send(self, page=trashed_item, user=None)

    def permanently_delete_item(self, trashed_item: Page, trash_item_lookup_cache=None):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestorePageOperationType.type
