from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.exceptions import (
    WidgetDoesNotExist,
    WidgetLayoutInvalid,
)
from baserow.contrib.dashboard.widgets.operations import (
    CreateWidgetOperationType,
    DeleteWidgetOperationType,
    ListWidgetsOperationType,
    ReadWidgetOperationType,
    UpdateWidgetLayoutOperationType,
    UpdateWidgetOperationType,
)
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler

from .grid_layout import fits_within_grid_columns, layouts_overlap
from .handler import WidgetHandler
from .models import Widget
from .signals import (
    widget_created,
    widget_deleted,
    widget_updated,
    widgets_layout_updated,
)
from .trash_types import WidgetTrashableItemType, widget_restore_context
from .types import CreatedWidget, UpdatedWidget, UpdatedWidgetLayout


class WidgetService:
    def __init__(self):
        self.handler = WidgetHandler()
        self.dashboard_handler = DashboardHandler()

    def _get_widgets_for_layout_mutation(
        self, dashboard: Dashboard
    ) -> tuple[list[Widget], bool]:
        """Locks a dashboard and its widgets before changing its layout.

        Locking the dashboard row serializes mutations even when it has no widgets
        yet. Locking only existing widgets would otherwise allow concurrent creates
        to select the same empty grid position.
        """

        Dashboard.objects.select_for_update(of=("self",)).get(id=dashboard.id)

        widgets = self.handler.get_widgets_for_update(dashboard)
        layouts_initialized = any(
            not widget.grid_layout_initialized for widget in widgets
        )
        self.handler.initialize_uninitialized_widget_grid_layouts(widgets)
        return widgets, layouts_initialized

    def _send_widgets_layout_updated(
        self,
        dashboard: Dashboard,
        user: AbstractUser | None = None,
    ) -> list[Widget]:
        """Publishes the complete canonical layout after a successful mutation."""

        widgets = list(self.handler.get_widgets(dashboard))
        widgets_layout_updated.send(
            self,
            user=user,
            dashboard=dashboard,
            widgets=widgets,
        )
        return widgets

    def get_widget(self, user: AbstractUser, widget_id: int) -> Widget:
        """
        Returns a widget instance from the database. Also checks the user permissions.

        :param user: The user trying to get the element
        :param widget_id: The ID of the widget.
        :raises WidgetDoesNotExist: If the widget can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
        :return: The widget instance.
        """

        widget = self.handler.get_widget(widget_id)

        if TrashHandler.item_has_a_trashed_parent(widget):
            raise WidgetDoesNotExist()

        CoreHandler().check_permissions(
            user,
            ReadWidgetOperationType.type,
            workspace=widget.dashboard.workspace,
            context=widget,
        )

        return widget

    @transaction.atomic
    def get_widgets(self, user: AbstractUser, dashboard_id: int) -> list[Widget]:
        """
        Gets all the widgets of a given dashboard.

        :param user: The user trying to get the widgets.
        :param dashboard_id: The Id of the dashboard that holds the widgets.
        :raises DashboardDoesNotExist: If the dashboard can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
        :return: The widgets of that dashboard.
        """

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)

        CoreHandler().check_permissions(
            user,
            ListWidgetsOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widgets = CoreHandler().filter_queryset(
            user,
            ListWidgetsOperationType.type,
            Widget.objects.all(),
            workspace=dashboard.workspace,
        )

        if Widget.objects.filter(
            dashboard=dashboard, grid_layout_initialized=False
        ).exists():
            _, layouts_initialized = self._get_widgets_for_layout_mutation(dashboard)
            if layouts_initialized:
                # This write repairs a layout created by an older application
                # process. It has no HTTP mutation response on other open clients,
                # so broadcast the canonical result to every dashboard subscriber.
                self._send_widgets_layout_updated(dashboard)

        return list(self.handler.get_widgets(dashboard, base_queryset=widgets))

    @transaction.atomic
    def create_widget(
        self,
        user: AbstractUser,
        widget_type: str,
        dashboard_id: int,
        order: int | None = None,
        **kwargs,
    ) -> Widget:
        """
        Creates a new widget for a dashboard given the user permissions.

        :param user: The user trying to create the widget.
        :param widget_type: The type of the widget.
        :param dashboard_id: The Id of the dashboard the widget should go in.
        :param order: If set, the new widget is inserted at this order.
        :param kwargs: Additional attributes of the widget.
        :raises WidgetTypeDoesNotExist: If the provided widget type
            does not exist.
        :raises DashboardDoesNotExist: If the dashboard can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
        :return: The created widget.
        """

        return self.create_widget_with_layout(
            user,
            widget_type,
            dashboard_id,
            order=order,
            **kwargs,
        ).widget

    @transaction.atomic
    def create_widget_with_layout(
        self,
        user: AbstractUser,
        widget_type: str,
        dashboard_id: int,
        order: int | None = None,
        **kwargs,
    ) -> CreatedWidget:
        """Creates a widget and returns the layout before and after the creation."""

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)

        CoreHandler().check_permissions(
            user,
            CreateWidgetOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widget_type_from_registry = widget_type_registry.get(widget_type)

        widget_type_from_registry.before_create(user, dashboard)
        widgets, layouts_initialized = self._get_widgets_for_layout_mutation(dashboard)
        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]

        new_widget = self.handler.create_widget(
            widget_type_from_registry,
            dashboard,
            existing_widgets=widgets,
            order=order,
            **kwargs,
        )

        if layouts_initialized:
            # A rollout-era widget was repaired while creating this widget. The full
            # snapshot includes both the repaired widgets and the new widget.
            self._send_widgets_layout_updated(dashboard)
        else:
            widget_created.send(self, user=user, widget=new_widget)

        return CreatedWidget(
            new_widget,
            original_layout,
            [*original_layout, self.handler.get_widget_layout(new_widget)],
        )

    def update_widget(
        self, user: AbstractUser, widget_id: int, **kwargs
    ) -> UpdatedWidget:
        """
        Updates a widget given the user permissions.

        :param user: The user trying to update the widget.
        :param widget_id: The ID of the widget to update.
        :param kwargs: Attributes of the widget.
        :raises WidgetDoesNotExist: If the widget can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
        :return: The updated widget.
        """

        widget = self.handler.get_widget_for_update(widget_id)

        if TrashHandler.item_has_a_trashed_parent(widget):
            raise WidgetDoesNotExist()

        CoreHandler().check_permissions(
            user,
            UpdateWidgetOperationType.type,
            workspace=widget.dashboard.workspace,
            context=widget,
        )

        updated_widget = self.handler.update_widget(widget, **kwargs)
        updated_widget = updated_widget.widget.get_type().after_update(
            updated_widget, **kwargs
        )
        widget_updated.send(self, user=user, widget=updated_widget.widget)
        return updated_widget

    def _validate_widget_layout(
        self,
        widgets: list[Widget],
        layout: list[dict[str, int]],
    ) -> dict[int, dict[str, int]]:
        """Validates a full layout against widget identities and type constraints."""

        if len(layout) != len(widgets):
            raise WidgetLayoutInvalid("The layout must include every dashboard widget.")

        layout_by_widget_id = {}
        for item in layout:
            try:
                widget_id = item["id"]
                grid_x = item["grid_x"]
                grid_y = item["grid_y"]
                grid_width = item["grid_width"]
                grid_height = item["grid_height"]
            except (KeyError, TypeError) as exc:
                raise WidgetLayoutInvalid("The layout item is incomplete.") from exc

            values = (widget_id, grid_x, grid_y, grid_width, grid_height)
            if any(type(value) is not int for value in values):
                raise WidgetLayoutInvalid("The layout values must be integers.")
            if widget_id in layout_by_widget_id:
                raise WidgetLayoutInvalid("A widget can only occur once in the layout.")
            if grid_x < 0 or grid_y < 0 or grid_width < 1 or grid_height < 1:
                raise WidgetLayoutInvalid(
                    "The layout contains an invalid grid position."
                )

            layout_by_widget_id[widget_id] = {
                "id": widget_id,
                "grid_x": grid_x,
                "grid_y": grid_y,
                "grid_width": grid_width,
                "grid_height": grid_height,
            }

        widget_ids = {widget.id for widget in widgets}
        if set(layout_by_widget_id) != widget_ids:
            raise WidgetLayoutInvalid(
                "The layout widgets do not match the dashboard widgets."
            )

        normalized_layout = []
        for widget in widgets:
            item = layout_by_widget_id[widget.id]
            constraints = widget.get_type().get_grid_layout()
            if not fits_within_grid_columns(item):
                raise WidgetLayoutInvalid(
                    "A widget cannot extend past the sixth column."
                )
            if not constraints.min_width <= item["grid_width"] <= constraints.max_width:
                raise WidgetLayoutInvalid("The widget width is outside of its limits.")
            if (
                not constraints.min_height
                <= item["grid_height"]
                <= constraints.max_height
            ):
                raise WidgetLayoutInvalid("The widget height is outside of its limits.")
            normalized_layout.append(item)

        for index, item in enumerate(normalized_layout):
            for other in normalized_layout[index + 1 :]:
                if layouts_overlap(item, other):
                    raise WidgetLayoutInvalid("Dashboard widgets cannot overlap.")

        return layout_by_widget_id

    @transaction.atomic
    def update_widget_layout(
        self,
        user: AbstractUser,
        dashboard_id: int,
        layout: list[dict[str, int]],
    ) -> UpdatedWidgetLayout:
        """Atomically persists a complete dashboard widget layout."""

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)
        CoreHandler().check_permissions(
            user,
            UpdateWidgetLayoutOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widgets, _ = self._get_widgets_for_layout_mutation(dashboard)
        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]
        layout_by_widget_id = self._validate_widget_layout(widgets, layout)
        self.handler.update_widget_layout(widgets, layout_by_widget_id)

        updated_widgets = self._send_widgets_layout_updated(dashboard, user)
        new_layout = [
            layout_by_widget_id[widget.id]
            for widget in sorted(widgets, key=lambda widget: widget.id)
        ]
        return UpdatedWidgetLayout(
            dashboard,
            updated_widgets,
            original_layout,
            new_layout,
        )

    def _delete_widget_and_apply_layout(
        self,
        user: AbstractUser,
        widget_id: int,
        layout: list[dict[str, int]] | None,
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and publishes the resulting canonical layout.

        ``layout`` is a complete snapshot of the remaining widgets when restoring a
        create/delete action. When it is omitted, deletion vertically compacts the
        remaining widgets. In both cases, moving other widgets is a consequence of
        a delete operation, so it deliberately requires only delete permission.
        """

        deleted_widget = self.handler.get_widget(widget_id)
        widget_id = deleted_widget.id

        if TrashHandler.item_has_a_trashed_parent(deleted_widget):
            raise WidgetDoesNotExist()

        dashboard = deleted_widget.dashboard
        CoreHandler().check_permissions(
            user,
            DeleteWidgetOperationType.type,
            workspace=dashboard.workspace,
            context=deleted_widget,
        )

        widgets, _ = self._get_widgets_for_layout_mutation(dashboard)
        widgets_by_id = {widget.id: widget for widget in widgets}
        widget = widgets_by_id.get(widget_id)
        if widget is None:
            raise WidgetDoesNotExist()

        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]
        remaining_widgets = [widget for widget in widgets if widget.id != widget_id]
        if layout is None:
            layout = self.handler.get_compacted_widget_layout(remaining_widgets)
            # Existing dashboards can still contain rollout-era geometry that is
            # outside the current type constraints. Compaction preserves that
            # geometry and is not a client-supplied layout to validate.
            layout_by_widget_id = {item["id"]: item for item in layout}
        else:
            layout_by_widget_id = self._validate_widget_layout(
                remaining_widgets, layout
            )

        TrashHandler.trash(user, dashboard.workspace, dashboard, widget)
        self.handler.update_widget_layout(remaining_widgets, layout_by_widget_id)

        updated_widgets = self._send_widgets_layout_updated(dashboard, user)
        new_layout = [
            layout_by_widget_id[widget.id]
            for widget in sorted(remaining_widgets, key=lambda widget: widget.id)
        ]
        return UpdatedWidgetLayout(
            dashboard,
            updated_widgets,
            original_layout,
            new_layout,
            deleted_widget,
        )

    @transaction.atomic
    def delete_widget_and_compact_layout(
        self, user: AbstractUser, widget_id: int
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and vertically compacts the remaining layout."""

        return self._delete_widget_and_apply_layout(user, widget_id, layout=None)

    @transaction.atomic
    def delete_widget_and_restore_layout(
        self,
        user: AbstractUser,
        widget_id: int,
        layout: list[dict[str, int]],
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and restores a recorded complete layout snapshot."""

        return self._delete_widget_and_apply_layout(user, widget_id, layout)

    def delete_widget(self, user: AbstractUser, widget_id: int) -> Widget:
        """
        Deletes the widget based on the provided widget id if the
        user has correct permissions to do so.

        :raises WidgetDoesNotExist: If the widget can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
        """

        updated_layout = self.delete_widget_and_compact_layout(user, widget_id)
        deleted_widget = updated_layout.deleted_widget
        assert deleted_widget is not None
        return deleted_widget

    @transaction.atomic
    def delete_widget_legacy(self, user: AbstractUser, widget_id: int) -> Widget:
        """Deletes a widget without applying grid behavior for a legacy action.

        Dashboard actions persisted before grid layouts existed do not contain a
        complete snapshot. Keep their original trash and WebSocket semantics rather
        than inferring a new layout while replaying them.
        """

        widget = self.handler.get_widget(widget_id)

        if TrashHandler.item_has_a_trashed_parent(widget):
            raise WidgetDoesNotExist()

        CoreHandler().check_permissions(
            user,
            DeleteWidgetOperationType.type,
            workspace=widget.dashboard.workspace,
            context=widget,
        )

        TrashHandler.trash(user, widget.dashboard.workspace, widget.dashboard, widget)
        widget_deleted.send(self, user=user, widget=widget)
        return widget

    @transaction.atomic
    def restore_widget_and_update_layout(
        self,
        user: AbstractUser,
        dashboard_id: int,
        widget_id: int,
        layout: list[dict[str, int]],
    ) -> UpdatedWidgetLayout:
        """Restores a widget and atomically restores a complete layout snapshot.

        The restore permission is the only permission required. Applying the saved
        layout is a consequence of the undo/redo operation, not a user-requested
        dashboard reorganization.
        """

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)
        self._get_widgets_for_layout_mutation(dashboard)

        with widget_restore_context(
            place_at_bottom=False,
            send_created_signal=False,
        ):
            TrashHandler.restore_item(user, WidgetTrashableItemType.type, widget_id)

        widgets = self.handler.get_widgets_for_update(dashboard)
        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]
        layout_by_widget_id = self._validate_widget_layout(widgets, layout)
        self.handler.update_widget_layout(widgets, layout_by_widget_id)
        updated_widgets = self._send_widgets_layout_updated(dashboard, user)
        new_layout = [
            layout_by_widget_id[widget.id]
            for widget in sorted(widgets, key=lambda widget: widget.id)
        ]
        return UpdatedWidgetLayout(
            dashboard,
            updated_widgets,
            original_layout,
            new_layout,
        )

    def restore_widget_legacy(self, user: AbstractUser, widget_id: int) -> Widget:
        """Restores a legacy action with the standard trash-restore behavior."""

        with widget_restore_context(
            place_at_bottom=True,
            send_created_signal=True,
        ):
            return TrashHandler.restore_item(
                user,
                WidgetTrashableItemType.type,
                widget_id,
            )
