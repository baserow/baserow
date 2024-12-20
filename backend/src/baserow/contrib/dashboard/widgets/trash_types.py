from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.operations import RestoreWidgetOperationType
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from .signals import widget_created


class WidgetTrashableItemType(TrashableItemType):
    type = "widget"
    model_class = Widget

    def get_parent(self, trashed_item: Widget) -> any:
        return trashed_item.dashboard

    def get_name(self, trashed_item: Widget) -> str:
        return trashed_item.title

    def restore(self, trashed_item: Widget, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)
        WidgetHandler().restore_widget(trashed_item.specific)
        widget_created.send(self, widget=trashed_item)

    def permanently_delete_item(
        self, trashed_item: Widget, trash_item_lookup_cache=None
    ):
        WidgetHandler().delete_widget(trashed_item.specific)

    def get_restore_operation_type(self) -> str:
        return RestoreWidgetOperationType.type
