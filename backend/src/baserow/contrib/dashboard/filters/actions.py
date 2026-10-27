from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.contrib.dashboard.actions import DASHBOARD_ACTION_CONTEXT
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType

from .service import DashboardFilterService


class CreateDashboardFilterActionType(UndoableActionType):
    type = "create_dashboard_filter"
    description = ActionTypeDescription(
        _("Create dashboard filter"),
        _('Filter "%(filter_label)s" (%(filter_id)s) created'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "filter_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        filter_id: int
        filter_label: str

    @classmethod
    @transaction.atomic
    def do(cls, user, dashboard_id, values):
        dashboard_filter = DashboardFilterService().create_filter(
            user, dashboard_id, **values
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                dashboard_id,
                dashboard_filter.dashboard.name,
                dashboard_filter.id,
                dashboard_filter.label,
            ),
            scope=cls.scope(dashboard_id),
            workspace=dashboard_filter.dashboard.workspace,
        )
        return dashboard_filter

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        DashboardFilterService().delete_filter(user, params.filter_id)

    @classmethod
    def redo(cls, user, params, action_to_redo):
        DashboardFilterService().restore_filter(user, params.filter_id)


class UpdateDashboardFilterActionType(UndoableActionType):
    type = "update_dashboard_filter"
    description = ActionTypeDescription(
        _("Update dashboard filter"),
        _('Filter "%(filter_label)s" (%(filter_id)s) updated'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "filter_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        filter_id: int
        filter_label: str
        previous: dict
        updated: dict

    @classmethod
    @transaction.atomic
    def do(cls, user, filter_id, values):
        dashboard_filter, previous, updated = DashboardFilterService().update_filter(
            user, filter_id, **values
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                dashboard_filter.dashboard_id,
                dashboard_filter.dashboard.name,
                dashboard_filter.id,
                dashboard_filter.label,
                previous,
                updated,
            ),
            scope=cls.scope(dashboard_filter.dashboard_id),
            workspace=dashboard_filter.dashboard.workspace,
        )
        return dashboard_filter

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        DashboardFilterService().update_filter(
            user, params.filter_id, **params.previous
        )

    @classmethod
    def redo(cls, user, params, action_to_redo):
        DashboardFilterService().update_filter(user, params.filter_id, **params.updated)


class DeleteDashboardFilterActionType(UndoableActionType):
    type = "delete_dashboard_filter"
    description = ActionTypeDescription(
        _("Delete dashboard filter"),
        _('Filter "%(filter_label)s" (%(filter_id)s) deleted'),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id", "filter_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        filter_id: int
        filter_label: str

    @classmethod
    @transaction.atomic
    def do(cls, user, filter_id):
        dashboard_filter = DashboardFilterService().delete_filter(user, filter_id)
        cls.register_action(
            user=user,
            params=cls.Params(
                dashboard_filter.dashboard_id,
                dashboard_filter.dashboard.name,
                dashboard_filter.id,
                dashboard_filter.label,
            ),
            scope=cls.scope(dashboard_filter.dashboard_id),
            workspace=dashboard_filter.dashboard.workspace,
        )

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        DashboardFilterService().restore_filter(user, params.filter_id)

    @classmethod
    def redo(cls, user, params, action_to_redo):
        DashboardFilterService().delete_filter(user, params.filter_id)


class OrderDashboardFiltersActionType(UndoableActionType):
    type = "order_dashboard_filters"
    description = ActionTypeDescription(
        _("Order dashboard filters"),
        _("Dashboard filter order changed"),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        previous: list[int]
        order: list[int]

    @classmethod
    @transaction.atomic
    def do(cls, user, dashboard_id, order):
        dashboard, previous, ordered = DashboardFilterService().order_filters(
            user, dashboard_id, order
        )
        cls.register_action(
            user=user,
            params=cls.Params(dashboard_id, dashboard.name, previous, ordered),
            scope=cls.scope(dashboard_id),
            workspace=dashboard.workspace,
        )

    @classmethod
    def scope(cls, dashboard_id):
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(cls, user, params, action_to_undo):
        DashboardFilterService().order_filters(
            user, params.dashboard_id, params.previous, ignore_missing=True
        )

    @classmethod
    def redo(cls, user, params, action_to_redo):
        DashboardFilterService().order_filters(
            user, params.dashboard_id, params.order, ignore_missing=True
        )
