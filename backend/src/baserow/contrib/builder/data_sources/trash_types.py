from typing import TYPE_CHECKING, Any, Optional

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    RestoreDataSourceOperationType,
)
from baserow.contrib.builder.data_sources.signals import (
    data_source_created,
    data_source_deleted,
)
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

if TYPE_CHECKING:
    from baserow.contrib.builder.pages.models import Page


class DataSourceTrashableItemType(TrashableItemType):
    type = "builder_data_source"
    model_class = DataSource

    def get_parent(self, trashed_item: DataSource) -> "Page":
        return trashed_item.page

    def get_name(self, trashed_item: DataSource) -> str:
        return f"{trashed_item.name} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: DataSource,
        requesting_user,
        trash_entry: TrashEntry,
    ) -> None:
        page = item_to_trash.page
        super().trash(item_to_trash, requesting_user, trash_entry)
        data_source_deleted.send(
            self,
            data_source_id=item_to_trash.id,
            page=page,
            user=requesting_user,
        )

    def restore(self, trashed_item: DataSource, trash_entry: TrashEntry) -> None:
        super().restore(trashed_item, trash_entry)
        data_source_created.send(
            self,
            data_source=trashed_item,
            user=None,
            before_id=None,
        )

    def permanently_delete_item(
        self, trashed_item: DataSource, trash_item_lookup_cache: Optional[Any] = None
    ) -> None:
        # Hard-deleting the data source fires the pre-delete receiver
        # (`before_data_source_permanently_deleted`) which cleans up the
        # underlying service. This only runs on permanent deletion, so a restore
        # brings the data source back with its service intact.
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreDataSourceOperationType.type
