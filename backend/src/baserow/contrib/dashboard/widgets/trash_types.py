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

    def trash(self, item_to_trash: Widget, requesting_user, trash_entry: TrashEntry):
        """Run widget hooks around the generic trash lifecycle."""
        item_to_trash = item_to_trash.specific
        widget_type = item_to_trash.get_type()
        widget_type.before_trashed(item_to_trash.specific, requesting_user, trash_entry)
        super().trash(item_to_trash, requesting_user, trash_entry)
        widget_type.after_trashed(item_to_trash.specific, requesting_user, trash_entry)

    def restore(self, trashed_item: Widget, trash_entry: TrashEntry):
        """Restore the widget and its layout, then run type-specific restoration."""
        trashed_item = trashed_item.specific
        # Widget placement is shared by all dashboard mutations, including a generic
        # trash restore which does not otherwise go through WidgetService.
        from baserow.contrib.dashboard.models import Dashboard

        Dashboard.objects.select_for_update(of=("self",)).get(
            id=trashed_item.dashboard_id
        )
        widget_type = trashed_item.get_type()
        widget_type.before_restore(trashed_item.specific, trash_entry)
        super().restore(trashed_item, trash_entry)
        WidgetHandler().place_restored_widget_at_bottom(trashed_item)
        widget_type.after_restore(trashed_item.specific, trash_entry)
        widget_created.send(self, widget=trashed_item)

    def permanently_delete_item(
        self, trashed_item: Widget, trash_item_lookup_cache=None
    ):
        WidgetHandler().delete_widget(trashed_item.specific)

    def get_restore_operation_type(self) -> str:
        return RestoreWidgetOperationType.type
