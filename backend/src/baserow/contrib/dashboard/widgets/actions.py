from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.contrib.dashboard.actions import DASHBOARD_ACTION_CONTEXT
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType

from .models import Widget
from .service import WidgetService


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
        # ``None`` identifies actions stored before grid layouts were introduced.
        # An empty list is a valid snapshot for a dashboard that had no widgets.
        original_layout: list[dict[str, int]] | None = None
        new_layout: list[dict[str, int]] | None = None

    @classmethod
    @transaction.atomic
    def do(
        cls, user: AbstractUser, dashboard_id: int, widget_type: str, data: dict
    ) -> Widget:
        widget_service = WidgetService()
        created_widget = widget_service.create_widget_with_layout(
            user, widget_type, dashboard_id, **data
        )
        widget = created_widget.widget
        cls.register_action(
            user=user,
            params=cls.Params(
                widget.dashboard.id,
                widget.dashboard.name,
                widget.id,
                widget.title,
                widget_type,
                created_widget.original_layout,
                created_widget.new_layout,
            ),
            scope=cls.scope(widget.dashboard.id),
            workspace=widget.dashboard.workspace,
        )
        return widget

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    @transaction.atomic
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        widget_service = WidgetService()
        if params.original_layout is None:
            widget_service.delete_widget_legacy(user, params.widget_id)
        else:
            widget_service.delete_widget_and_restore_layout(
                user,
                params.widget_id,
                params.original_layout,
            )

    @classmethod
    @transaction.atomic
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        widget_service = WidgetService()
        if params.new_layout is None:
            widget_service.restore_widget_legacy(user, params.widget_id)
        else:
            widget_service.restore_widget_and_update_layout(
                user,
                params.dashboard_id,
                params.widget_id,
                params.new_layout,
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


class UpdateWidgetLayoutActionType(UndoableActionType):
    type = "update_widget_layout"
    description = ActionTypeDescription(
        _("Update widget layout"),
        _("Dashboard widget layout updated"),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        original_layout: list[dict[str, int]]
        new_layout: list[dict[str, int]]

    @classmethod
    @transaction.atomic
    def do(
        cls,
        user: AbstractUser,
        dashboard_id: int,
        new_layout: list[dict[str, int]],
    ) -> list[Widget]:
        updated_layout = WidgetService().update_visible_widget_layout(
            user, dashboard_id, new_layout
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                updated_layout.dashboard.id,
                updated_layout.dashboard.name,
                updated_layout.original_layout,
                updated_layout.new_layout,
            ),
            scope=cls.scope(updated_layout.dashboard.id),
            workspace=updated_layout.dashboard.workspace,
        )
        return updated_layout.widgets

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
        WidgetService().update_widget_layout(
            user,
            params.dashboard_id,
            params.original_layout,
            enforce_vertical_bound=False,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        WidgetService().update_widget_layout(
            user,
            params.dashboard_id,
            params.new_layout,
            enforce_vertical_bound=False,
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
        # ``None`` identifies actions stored before grid layouts were introduced.
        # An empty list is a valid snapshot for a dashboard without widgets.
        original_layout: list[dict[str, int]] | None = None
        new_layout: list[dict[str, int]] | None = None

    @classmethod
    @transaction.atomic
    def do(cls, user: AbstractUser, widget_id: int) -> None:
        updated_layout = WidgetService().delete_widget_and_compact_layout(
            user, widget_id
        )
        deleted_widget = updated_layout.deleted_widget
        assert deleted_widget is not None
        cls.register_action(
            user=user,
            params=cls.Params(
                updated_layout.dashboard.id,
                updated_layout.dashboard.name,
                deleted_widget.id,
                deleted_widget.title,
                updated_layout.original_layout,
                updated_layout.new_layout,
            ),
            scope=cls.scope(updated_layout.dashboard.id),
            workspace=updated_layout.dashboard.workspace,
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
        widget_service = WidgetService()
        if params.original_layout is None:
            widget_service.restore_widget_legacy(user, params.widget_id)
        else:
            widget_service.restore_widget_and_update_layout(
                user,
                params.dashboard_id,
                params.widget_id,
                params.original_layout,
            )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        widget_service = WidgetService()
        if params.new_layout is None:
            widget_service.delete_widget_legacy(user, params.widget_id)
        else:
            widget_service.delete_widget_and_restore_layout(
                user,
                params.widget_id,
                params.new_layout,
            )
