import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    VIEW_ACTION_CONTEXT,
    ViewActionScopeType,
)
from baserow.contrib.database.admin.views.handler import ViewsAdminHandler
from baserow.contrib.database.views.models import View
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)


class UpdateViewPublicAdminActionType(ActionType):
    type = "admin_update_view_public"
    description = ActionTypeDescription(
        _("Admin changed view public sharing"),
        _(
            'Admin "%(user_email)s" (%(user_id)s) changed the publicly shared '
            "state to %(public)s "
        ),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "public",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        public: bool
        original_public: bool

    @classmethod
    def do(cls, user: AbstractUser, view: View, public: bool) -> View:
        original_public = view.public

        view = ViewsAdminHandler().update_view_public(user, view, public)

        cls.register_action(
            user=user,
            params=cls.Params(
                user.id,
                user.email,
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view.public,
                original_public,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )
        return view

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)


class RotateViewSlugAdminActionType(ActionType):
    type = "admin_rotate_view_slug"
    description = ActionTypeDescription(
        _("Admin rotated view slug"),
        _('Admin "%(user_email)s" (%(user_id)s) rotated the public slug URL '),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        slug: str
        original_slug: str

    @classmethod
    def do(cls, user: AbstractUser, view: View) -> View:
        original_slug = view.slug

        view = ViewsAdminHandler().rotate_view_slug(user, view)

        cls.register_action(
            user=user,
            params=cls.Params(
                user.id,
                user.email,
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view.slug,
                original_slug,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )
        return view

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)
