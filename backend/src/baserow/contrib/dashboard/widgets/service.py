from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
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
from .layout import WidgetLayoutHandler
from .models import Widget
from .signals import (
    widget_created,
    widget_deleted,
    widget_updated,
    widgets_layout_updated,
)
from .trash_types import WidgetTrashableItemType
from .types import (
    CreatedWidget,
    UpdatedWidget,
    UpdatedWidgetLayout,
    WidgetLayoutDelta,
    WidgetLayoutDict,
)


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
    ) -> None:
        """Publishes a non-sensitive invalidation after a layout mutation."""

        widgets_layout_updated.send(
            self,
            user=user,
            dashboard=dashboard,
        )

    def _layout_update_result(
        self,
        user: AbstractUser | None,
        dashboard: Dashboard,
        layout_delta: WidgetLayoutDelta,
        *,
        visible_layout: list[WidgetLayoutDict] | None = None,
        deleted_widget: Widget | None = None,
        force_invalidation: bool = False,
    ) -> UpdatedWidgetLayout:
        """Builds the service result and publishes a current-client invalidation."""

        if force_invalidation or layout_delta.has_changes:
            self._send_widgets_layout_updated(dashboard, user)
        return UpdatedWidgetLayout(
            dashboard,
            layout_delta,
            visible_layout=visible_layout,
            deleted_widget=deleted_widget,
        )

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
        original_layout = WidgetLayoutHandler(widgets).current_layout
        new_widget = self.handler.create_widget(
            widget_type_from_registry,
            dashboard,
            existing_widgets=widgets,
            order=order,
            **kwargs,
        )

        new_layout = [*original_layout, WidgetLayoutHandler.from_widget(new_widget)]
        widget_created.send(self, user=user, widget=new_widget)
        # Keep the pre-grid event for clients running the previous frontend bundle,
        # and publish the canonical invalidation understood by current clients.
        self._send_widgets_layout_updated(
            dashboard,
            None if layouts_initialized else user,
        )

        return CreatedWidget(
            new_widget,
            WidgetLayoutDelta.between(original_layout, new_layout),
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

    @transaction.atomic
    def update_widget_layout(
        self,
        user: AbstractUser,
        dashboard_id: int,
        layout: list[WidgetLayoutDict],
        *,
        enforce_vertical_bound: bool = True,
    ) -> UpdatedWidgetLayout:
        """Merges and persists a recorded delta against the current layout."""

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)
        CoreHandler().check_permissions(
            user,
            UpdateWidgetLayoutOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widgets, layouts_initialized = self._get_widgets_for_layout_mutation(dashboard)
        layout_delta = WidgetLayoutHandler(widgets).apply_delta(
            layout,
            enforce_vertical_bound=enforce_vertical_bound,
        )
        return self._layout_update_result(
            None if layouts_initialized else user,
            dashboard,
            layout_delta,
            force_invalidation=layouts_initialized,
        )

    @transaction.atomic
    def update_visible_widget_layout(
        self,
        user: AbstractUser,
        dashboard_id: int,
        layout: list[WidgetLayoutDict],
    ) -> UpdatedWidgetLayout:
        """Updates only widgets visible to ``user`` and preserves hidden geometry."""

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)
        core_handler = CoreHandler()
        core_handler.check_permissions(
            user,
            UpdateWidgetLayoutOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )
        core_handler.check_permissions(
            user,
            ListWidgetsOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        widgets, layouts_initialized = self._get_widgets_for_layout_mutation(dashboard)
        visible_queryset = core_handler.filter_queryset(
            user,
            ListWidgetsOperationType.type,
            Widget.objects.filter(id__in=[widget.id for widget in widgets]),
            workspace=dashboard.workspace,
        )
        visible_widget_ids = set(visible_queryset.values_list("id", flat=True))
        visible_widgets = [
            widget for widget in widgets if widget.id in visible_widget_ids
        ]
        hidden_layout = [
            WidgetLayoutHandler.from_widget(widget)
            for widget in widgets
            if widget.id not in visible_widget_ids
        ]

        # Validate identities and type constraints against exactly the visible
        # snapshot first. Hidden widgets stay fixed obstacles during canonical
        # compaction; the merged layout below checks complete collisions and bounds.
        visible_layout_by_widget_id = WidgetLayoutHandler(visible_widgets).validate(
            layout,
            compact=True,
            fixed_layouts=hidden_layout,
            existing_grid_bottom=max(
                (widget.grid_y + widget.grid_height for widget in widgets),
                default=0,
            ),
        )
        widget_layout_handler = WidgetLayoutHandler(widgets)
        merged_layout = [
            visible_layout_by_widget_id.get(
                widget.id, WidgetLayoutHandler.from_widget(widget)
            )
            for widget in widgets
        ]
        # The client-controlled visible part is already compacted. Do not reject an
        # otherwise valid edit because a preserved hidden/rollout-era widget has a
        # large vertical gap outside the current defensive request bound.
        merged_layout_by_widget_id = widget_layout_handler.validate(
            merged_layout,
            enforce_vertical_bound=False,
        )
        layout_delta = widget_layout_handler.apply(
            merged_layout_by_widget_id,
            allowed_widget_ids=visible_widget_ids,
        )
        visible_layout = sorted(
            visible_layout_by_widget_id.values(),
            key=lambda item: (item["grid_y"], item["grid_x"], item["id"]),
        )
        return self._layout_update_result(
            None if layouts_initialized else user,
            dashboard,
            layout_delta,
            visible_layout=visible_layout,
            force_invalidation=layouts_initialized,
        )

    def _delete_widget_and_apply_layout(
        self,
        user: AbstractUser,
        widget_id: int,
        layout: list[WidgetLayoutDict] | None,
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and publishes the resulting canonical layout.

        ``layout`` is the recorded delta for remaining widgets when replaying a
        create/delete action. When omitted, deletion vertically compacts the layout.
        Moving other widgets is a consequence of deletion, so it deliberately
        requires only delete permission.
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

        original_layout = WidgetLayoutHandler(widgets).current_layout
        remaining_widgets = [widget for widget in widgets if widget.id != widget_id]
        remaining_layout_handler = WidgetLayoutHandler(remaining_widgets)
        if layout is None:
            layout = remaining_layout_handler.compacted_layout
            # Existing dashboards can still contain rollout-era geometry that is
            # outside the current type constraints. Compaction preserves that
            # geometry and is not a client-supplied layout to validate.
            layout_by_widget_id = {item["id"]: item for item in layout}
        else:
            _, layout_by_widget_id = remaining_layout_handler.merge_delta(
                layout,
                enforce_vertical_bound=False,
            )

        layout_delta = remaining_layout_handler.apply(
            layout_by_widget_id,
            original_layout=original_layout,
        )
        TrashHandler.trash(user, dashboard.workspace, dashboard, widget)
        widget_deleted.send(self, user=user, widget=deleted_widget)
        return self._layout_update_result(
            user,
            dashboard,
            layout_delta,
            deleted_widget=deleted_widget,
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
        layout: list[WidgetLayoutDict],
    ) -> UpdatedWidgetLayout:
        """Trashes a widget and applies the recorded layout delta."""

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
        layout: list[WidgetLayoutDict],
    ) -> UpdatedWidgetLayout:
        """Restores a widget and atomically applies a recorded layout delta.

        The restore permission is the only permission required. Applying the saved
        layout is a consequence of the undo/redo operation, not a user-requested
        dashboard reorganization.
        """

        dashboard = self.dashboard_handler.get_dashboard(dashboard_id)
        self._get_widgets_for_layout_mutation(dashboard)

        restored_widget = TrashHandler.restore_item(
            user,
            WidgetTrashableItemType.type,
            widget_id,
        )

        widgets = self.handler.get_widgets_for_update(dashboard)
        layout_delta = WidgetLayoutHandler(widgets).apply_delta(
            layout,
            enforce_vertical_bound=False,
        )
        updated_layout = self._layout_update_result(
            user,
            dashboard,
            layout_delta,
            force_invalidation=True,
        )
        # The widget_created WebSocket callback serializes this instance on commit.
        # Refresh it after applying the delta so legacy clients receive final geometry.
        restored_widget.refresh_from_db()
        return updated_layout

    def restore_widget_legacy(self, user: AbstractUser, widget_id: int) -> Widget:
        """Restores a legacy action with the standard trash-restore behavior."""

        return TrashHandler.restore_item(
            user,
            WidgetTrashableItemType.type,
            widget_id,
        )
