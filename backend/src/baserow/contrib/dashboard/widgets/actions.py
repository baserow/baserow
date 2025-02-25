from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.dashboard.actions import DASHBOARD_ACTION_CONTEXT
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler

from .models import Widget
from .service import WidgetService
from .trash_types import WidgetTrashableItemType


class CreateWidgetActionType(UndoableActionType):
    type = "create_widget"
    description = ActionTypeDescription(
        _("Create widget"),
        _('Widget "%(widget_title)s" (%(widget_id)s) created'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "widget_id", "widget_type"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        widget_id: int
        widget_title: str
        widget_type: str

    @classmethod
    def do(
        cls, user: AbstractUser, dashboard_id: int, widget_type: str, data: dict
    ) -> Widget:
        widget = WidgetService().create_widget(user, widget_type, dashboard_id, **data)
        cls.register_action(
            user=user,
            params=cls.Params(
                widget.dashboard.id,
                widget.dashboard.name,
                widget.id,
                widget.title,
                widget_type,
            ),
            scope=cls.scope(widget.dashboard.id),
            workspace=widget.dashboard.workspace,
        )
        return widget

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        WidgetService().delete_widget(user, params.widget_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user,
            WidgetTrashableItemType.type,
            params.widget_id,
        )


class UpdateWidgetActionType(UndoableActionType):
    type = "update_widget"
    description = ActionTypeDescription(
        _("Update widget"),
        _('Widget "%(widget_title)s" (%(widget_id)s) updated'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "widget_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        widget_id: int
        widget_title: str
        widget_type: str
        widget_original_params: dict[str, any]
        widget_new_params: dict[str, any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        widget_id: int,
        widget_type: str,
        new_data: dict,
    ) -> Widget:
        updated_widget = WidgetService().update_widget(user, widget_id, **new_data)
        cls.register_action(
            user=user,
            params=cls.Params(
                updated_widget.widget.dashboard.id,
                updated_widget.widget.dashboard.name,
                updated_widget.widget.id,
                updated_widget.widget.title,
                widget_type,
                updated_widget.original_values,
                updated_widget.new_values,
            ),
            scope=cls.scope(updated_widget.widget.dashboard.id),
            workspace=updated_widget.widget.dashboard.workspace,
        )
        return updated_widget.widget

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        WidgetService().update_widget(
            user, params.widget_id, **params.widget_original_params
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        WidgetService().update_widget(
            user, params.widget_id, **params.widget_new_params
        )


class DeleteWidgetActionType(UndoableActionType):
    type = "delete_widget"
    description = ActionTypeDescription(
        _("Delete widget"),
        _('Widget "%(widget_title)s" (%(widget_id)s) deleted'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "widget_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        widget_id: int
        widget_title: str

    @classmethod
    def do(cls, user: AbstractUser, widget_id: int) -> None:
        widget = WidgetService().delete_widget(user, widget_id)
        cls.register_action(
            user=user,
            params=cls.Params(
                widget.dashboard.id,
                widget.dashboard.name,
                widget.id,
                widget.title,
            ),
            scope=cls.scope(widget.dashboard.id),
            workspace=widget.dashboard.workspace,
        )

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        TrashHandler.restore_item(
            user,
            WidgetTrashableItemType.type,
            params.widget_id,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        WidgetService().delete_widget(user, params.widget_id)
