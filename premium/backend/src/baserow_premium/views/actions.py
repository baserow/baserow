import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    VIEW_ACTION_CONTEXT,
    ViewActionScopeType,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow_premium.views.models import CalendarView

ICAL_SLUG_FIELD = "ical_slug"


class RotateCalendarIcalSlugActionType(UndoableActionType):
    type = "rotate_calendar_ical_view_slug"
    description = ActionTypeDescription(
        _("Calendar View ICal feed slug URL updated"),
        _("View changed public ICal feed slug URL"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        slug: str
        original_slug: str

    @classmethod
    def do(cls, user: AbstractUser, view: CalendarView) -> View:
        """
        Change the ical feed slug for the current view.
        See baserow.contrib.database.views.handler.ViewHandler.rotate_slug for more.
        Undoing this action restores the original slug.
        Redoing this action updates the slug to the new one.

        :param user: The user rotating the slug
        :param view: The view of the slug to update.
        """

        original_slug = view.ical_slug

        ViewHandler().rotate_view_slug(user, view, slug_field=ICAL_SLUG_FIELD)

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view.ical_slug,
                original_slug,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )
        return view

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id).specific
        view_handler.update_view_slug(
            user, view, params.original_slug, slug_field=ICAL_SLUG_FIELD
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id).specific
        view_handler.update_view_slug(
            user, view, params.slug, slug_field=ICAL_SLUG_FIELD
        )
