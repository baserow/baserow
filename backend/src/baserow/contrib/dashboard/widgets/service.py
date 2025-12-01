from django.contrib.auth.models import AbstractUser

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.operations import (
    CreateWidgetOperationType,
    DeleteWidgetOperationType,
    ListWidgetsOperationType,
    ReadWidgetOperationType,
    UpdateWidgetOperationType,
)
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler

from .handler import WidgetHandler
from .models import Widget
from .signals import widget_created, widget_deleted, widget_updated
from .types import UpdatedWidget


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

    def delete_widget(self, user: AbstractUser, widget_id: int) -> Widget:
        """
        Deletes the widget based on the provided widget id if the
        user has correct permissions to do so.

        :raises WidgetDoesNotExist: If the widget can't be found.
        :raises PermissionException: Raised when user doesn't have the
            correct permission.
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
