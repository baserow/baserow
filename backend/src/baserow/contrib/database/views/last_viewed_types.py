from typing import Iterable

from django.db.models import QuerySet

from baserow.contrib.database.trash.trash_types import (
    TableTrashableItemType,
    ViewTrashableItemType,
)
from baserow.contrib.database.views.models import View
from baserow.core.registries import LastViewedItemType


class DatabaseViewLastViewedItemType(LastViewedItemType):
    type = "database_view"
    model_class = View

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        # `Database` is a child of `Application`, so this join also brings the
        # workspace id along. Trashing a table or database does not flag its views,
        # hence the explicit parent filters.
        return View.objects.select_related("table__database").filter(
            table__trashed=False,
            table__database__trashed=False,
            table__database__workspace__trashed=False,
            table__database__workspace__workspaceuser__user_id=user_id,
        )

    def get_application_id(self, instance: View) -> int:
        return instance.table.database_id

    def get_workspace_id(self, instance: View) -> int:
        return instance.table.database.workspace_id

    def get_item_ids_of_permanently_deleted(
        self, trash_item_type: str, trash_item
    ) -> Iterable[int]:
        if trash_item_type == ViewTrashableItemType.type:
            return [trash_item.id]
        if trash_item_type == TableTrashableItemType.type:
            return View.objects_and_trash.filter(table_id=trash_item.id).values_list(
                "id", flat=True
            )
        return []
