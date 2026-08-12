from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.dashboard.handler import DashboardHandler
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

from .handler import WidgetHandler
from .models import Widget
from .signals import (
    widget_created,
    widget_deleted,
    widget_updated,
    widgets_layout_updated,
)
from .types import UpdatedWidget, UpdatedWidgetLayout


class WidgetService:
    def __init__(self):
        self.handler = WidgetHandler()
        self.dashboard_handler = DashboardHandler()

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

        return self.handler.get_widgets(dashboard, base_queryset=widgets)

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

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)

        CoreHandler().check_permissions(
            user,
            CreateWidgetOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widget_type_from_registry = widget_type_registry.get(widget_type)

        widget_type_from_registry.before_create(user, dashboard)

        new_widget = self.handler.create_widget(
            widget_type_from_registry,
            dashboard,
            order=order,
            **kwargs,
        )

        widget_created.send(self, user=user, widget=new_widget)

        return new_widget

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
            if item["grid_x"] + item["grid_width"] > 6:
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
                overlaps_horizontally = (
                    item["grid_x"] < other["grid_x"] + other["grid_width"]
                    and other["grid_x"] < item["grid_x"] + item["grid_width"]
                )
                overlaps_vertically = (
                    item["grid_y"] < other["grid_y"] + other["grid_height"]
                    and other["grid_y"] < item["grid_y"] + item["grid_height"]
                )
                if overlaps_horizontally and overlaps_vertically:
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

        widgets = self.handler.get_widgets_for_update(dashboard)
        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]
        layout_by_widget_id = self._validate_widget_layout(widgets, layout)
        self.handler.update_widget_layout(widgets, layout_by_widget_id)

        updated_widgets = list(self.handler.get_widgets(dashboard))
        new_layout = [
            layout_by_widget_id[widget.id]
            for widget in sorted(widgets, key=lambda widget: widget.id)
        ]
        widgets_layout_updated.send(
            self,
            user=user,
            dashboard=dashboard,
            widgets=updated_widgets,
        )
        return UpdatedWidgetLayout(
            dashboard,
            updated_widgets,
            original_layout,
            new_layout,
        )

    @transaction.atomic
    def delete_widget_and_compact_layout(
        self, user: AbstractUser, widget_id: int
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and compacts the remaining widgets vertically.

        This keeps the legacy single-widget deletion endpoint compatible with the
        persisted grid. The automatic compaction is a consequence of deleting the
        widget, so it intentionally requires the delete permission rather than the
        dashboard-wide layout permission used by client-supplied layouts.
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

        widgets = self.handler.get_widgets_for_update(dashboard)
        widgets_by_id = {widget.id: widget for widget in widgets}
        widget = widgets_by_id.get(widget_id)
        if widget is None:
            raise WidgetDoesNotExist()

        original_layout = [self.handler.get_widget_layout(widget) for widget in widgets]
        remaining_widgets = [widget for widget in widgets if widget.id != widget_id]
        compacted_layout = self.handler.get_compacted_widget_layout(remaining_widgets)
        layout_by_widget_id = {layout["id"]: layout for layout in compacted_layout}

        TrashHandler.trash(user, dashboard.workspace, dashboard, widget)
        self.handler.update_widget_layout(remaining_widgets, layout_by_widget_id)

        updated_widgets = list(self.handler.get_widgets(dashboard))
        new_layout = [
            layout_by_widget_id[widget.id]
            for widget in sorted(remaining_widgets, key=lambda widget: widget.id)
        ]
        widget_deleted.send(self, user=user, widget=deleted_widget)
        widgets_layout_updated.send(
            self,
            user=user,
            dashboard=dashboard,
            widgets=updated_widgets,
        )
        return UpdatedWidgetLayout(
            dashboard,
            updated_widgets,
            original_layout,
            new_layout,
            deleted_widget,
        )

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
