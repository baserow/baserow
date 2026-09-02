from typing import Iterable

from django.db.models import QuerySet

from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.trash_types import PageTrashableItemType
from baserow.core.registries import LastViewedItemType


class BuilderPageLastViewedItemType(LastViewedItemType):
    type = "builder_page"
    model_class = Page

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        # The shared page is loaded on every builder visit, so it never counts as
        # viewed, whichever path leads here.
        return Page.objects_without_shared.select_related("builder").filter(
            builder__trashed=False,
            builder__workspace__trashed=False,
            builder__workspace__workspaceuser__user_id=user_id,
        )

    def get_application_id(self, instance: Page) -> int:
        return instance.builder_id

    def get_workspace_id(self, instance: Page) -> int:
        return instance.builder.workspace_id

    def get_item_ids_of_permanently_deleted(
        self, trash_item_type: str, trash_item
    ) -> Iterable[int]:
        if trash_item_type == PageTrashableItemType.type:
            return [trash_item.id]
        return []
