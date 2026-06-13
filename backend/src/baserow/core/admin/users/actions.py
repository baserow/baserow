import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType
from baserow.core.admin.users.handler import UserAdminHandler


class AdminDisableTwoFactorAuthActionType(ActionType):
    type = "admin_disable_two_factor_auth"
    description = ActionTypeDescription(
        _("Admin disable two-factor authentication"),
        _(
            'Admin "%(user_email)s" (%(user_id)s) disabled two-factor '
            'authentication of user "%(disabled_user_email)s" '
            "(%(disabled_user_id)s)."
        ),
    )
    analytics_params = [
        "user_id",
        "disabled_user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        disabled_user_id: int
        disabled_user_email: str

    @classmethod
    def do(cls, requesting_user: AbstractUser, user_id: int) -> None:
        """
        Removes the two-factor authentication of the specified user on behalf
        of an instance admin.

        :param requesting_user: The staff user performing the action.
        :param user_id: The id of the user whose two-factor authentication
            must be removed.
        """

        user = UserAdminHandler().disable_user_two_factor_auth(requesting_user, user_id)

        cls.register_action(
            user=requesting_user,
            params=cls.Params(
                requesting_user.id,
                requesting_user.email,
                user.id,
                user.email,
            ),
            scope=cls.scope(),
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
