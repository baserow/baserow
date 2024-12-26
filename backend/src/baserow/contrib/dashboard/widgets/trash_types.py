from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.operations import RestoreWidgetOperationType
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
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

    def trash(self, item_to_trash: Widget, requesting_user, trash_entry: TrashEntry):
        widget_type = widget_type_registry.get_by_model(item_to_trash.specific)
        widget_type.before_trashed(item_to_trash.specific)
        super().trash(item_to_trash, requesting_user, trash_entry)

    def restore(self, trashed_item: Widget, trash_entry: TrashEntry):
        widget_type = widget_type_registry.get_by_model(trashed_item.specific)
        widget_type.before_restore(trashed_item.specific)
        super().restore(trashed_item, trash_entry)
        widget_created.send(self, widget=trashed_item)

    def permanently_delete_item(
        self, trashed_item: Widget, trash_item_lookup_cache=None
    ):
        WidgetHandler().delete_widget(trashed_item.specific)

    def get_restore_operation_type(self) -> str:
        return RestoreWidgetOperationType.type
