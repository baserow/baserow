from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
    render_action_type_description,
)
from baserow.core.action.scopes import ApplicationActionScopeType

from .handler import DashboardHandler
from .models import Dashboard
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


class UpdateDashboardSharingActionType(UndoableActionType):
    type = "update_dashboard_sharing"
    description = ActionTypeDescription(
        _("Update dashboard sharing"),
        _("Sharing settings updated"),
        DASHBOARD_ACTION_CONTEXT,
    )
    analytics_params = ["dashboard_id"]

    @dataclass
    class Params:
        dashboard_id: int
        dashboard_name: str
        # Only the provided sharing fields. `public_password` is the hash, never
        # the password itself, exactly like `public_view_password` of views.
        data: dict[str, Any]
        original_data: dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, dashboard_id: int, **values) -> Dashboard:
        """
        Updates the public sharing state of the dashboard: `public`,
        `public_password` (already hashed, an empty string removes it) and
        `show_logo`. Undoing restores the original values of the provided fields,
        redoing applies the new values again.

        :param user: The user on whose behalf the sharing state is updated.
        :param dashboard_id: The Id of the dashboard to update.
        :param values: The new values of the sharing fields.
        :return: The updated dashboard.
        """

        result = DashboardService().update_sharing(user, dashboard_id, **values)
        dashboard = result.dashboard

        cls.register_action(
            user=user,
            params=cls.Params(
                dashboard.id,
                dashboard.name,
                result.new_values,
                result.original_values,
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
        DashboardService().update_sharing(
            user, params.dashboard_id, **params.original_data
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        DashboardService().update_sharing(user, params.dashboard_id, **params.data)

    @classmethod
    def get_long_description(cls, params_dict: dict[str, Any], *args, **kwargs) -> str:
        # The changes are put into words here rather than stored in `Params`, so
        # they are translated when the audit log is read, like the rest of the
        # description.
        changes = cls.describe_changes(
            params_dict.get("data") or {}, params_dict.get("original_data") or {}
        )
        description = ActionTypeDescription(
            cls.description.short,
            _("Sharing settings updated (%(changes)s)"),
            cls.description.context,
        )
        return render_action_type_description(
            description,
            {**params_dict, "changes": ", ".join(str(change) for change in changes)},
        )

    @staticmethod
    def describe_changes(
        data: dict[str, Any], original_data: dict[str, Any]
    ) -> list[str]:
        """
        Puts into words what the action changed, for the audit log. The password
        itself never appears, only whether one was set, changed or removed.

        :param data: The new values of the provided sharing fields.
        :param original_data: The values of the same fields before the update.
        :return: One phrase per change.
        """

        changes = []

        if "public" in data and data["public"] != original_data.get("public"):
            changes.append(_("made public") if data["public"] else _("made private"))

        if "public_password" in data:
            had_password = bool(original_data.get("public_password"))
            has_password = bool(data["public_password"])
            if has_password and not had_password:
                changes.append(_("password set"))
            elif had_password and not has_password:
                changes.append(_("password removed"))
            elif (
                has_password
                and data["public_password"] != original_data["public_password"]
            ):
                changes.append(_("password changed"))

        if "show_logo" in data and data["show_logo"] != original_data.get("show_logo"):
            changes.append(
                _("Baserow logo shown")
                if data["show_logo"]
                else _("Baserow logo hidden")
            )

        if not changes:
            changes.append(_("nothing changed"))

        return changes
