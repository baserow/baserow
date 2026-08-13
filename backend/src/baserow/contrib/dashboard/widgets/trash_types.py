from contextlib import contextmanager
from contextvars import ContextVar

from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.operations import RestoreWidgetOperationType
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from .signals import widget_created

_widget_restore_options = ContextVar(
    "dashboard_widget_restore_options",
    default=(True, True),
)


@contextmanager
def widget_restore_context(*, place_at_bottom: bool, send_created_signal: bool):
    """Temporarily controls the side effects of a widget trash restore.

    Generic trash restores append the restored widget to the current layout and
    announce it as a newly available widget. An undo/redo operation restores a
    complete layout immediately afterwards, so it must suppress those transient
    side effects and publish only the resulting canonical layout.
    """

    token = _widget_restore_options.set((place_at_bottom, send_created_signal))
    try:
        yield
    finally:
        _widget_restore_options.reset(token)


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
        # Widget placement is shared by all dashboard mutations, including a generic
        # trash restore which does not otherwise go through WidgetService.
        from baserow.contrib.dashboard.models import Dashboard

        place_at_bottom, send_created_signal = _widget_restore_options.get()
        Dashboard.objects.select_for_update(of=("self",)).get(
            id=trashed_item.dashboard_id
        )
        widget_type = widget_type_registry.get_by_model(trashed_item.specific)
        widget_type.before_restore(trashed_item.specific)
        super().restore(trashed_item, trash_entry)
        if place_at_bottom:
            WidgetHandler().place_restored_widget_at_bottom(trashed_item)
        if send_created_signal:
            widget_created.send(self, widget=trashed_item)

    def permanently_delete_item(
        self, trashed_item: Widget, trash_item_lookup_cache=None
    ):
        WidgetHandler().delete_widget(trashed_item.specific)

    def get_restore_operation_type(self) -> str:
        return RestoreWidgetOperationType.type
