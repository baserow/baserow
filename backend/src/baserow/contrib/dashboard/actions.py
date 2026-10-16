from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import ApplicationActionScopeType

from .handler import DashboardHandler
from .service import DashboardService

DASHBOARD_ACTION_CONTEXT = _('in dashboard "%(dashboard_name)s" (%(dashboard_id)s).')


class RotateDashboardSlugActionType(UndoableActionType):
    type = "rotate_dashboard_slug"
    description = ActionTypeDescription(
        _("Rotate dashboard slug"),
        _("Dashboard public URL slug rotated"),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        slug: str
        original_slug: str

    @classmethod
    def do(cls, user: AbstractUser, dashboard_id: int):
        """
        Replaces the public slug of the dashboard with a new one. Undoing restores
        the original slug, redoing applies the new slug again.

        :param user: The user on whose behalf the slug is rotated.
        :param dashboard_id: The Id of the dashboard to update.
        :return: The updated dashboard.
        """

        original_slug = DashboardHandler().get_dashboard(dashboard_id).slug
        dashboard = DashboardService().rotate_slug(user, dashboard_id)

        cls.register_action(
            user=user,
            params=cls.Params(
                dashboard.id,
                dashboard.name,
                dashboard.slug,
                original_slug,
            ),
            scope=cls.scope(dashboard.id),
            workspace=dashboard.workspace,
        )
        return dashboard

    @classmethod
    def scope(cls, dashboard_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(dashboard_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        DashboardService().update_slug(user, params.dashboard_id, params.original_slug)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        DashboardService().update_slug(user, params.dashboard_id, params.slug)
