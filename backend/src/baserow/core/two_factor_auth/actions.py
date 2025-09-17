import dataclasses
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)

from django.contrib.auth.models import AbstractUser

from baserow.core.action.scopes import RootActionScopeType


class ConfigureTwoFactorAuthActionType(ActionType):
    type = "configure_two_factor_auth"
    description = ActionTypeDescription(
        _("Configure two-factor authentication"),
        _('User "%(user_email)s" (%(user_id)s) configured two-factor authentication.'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(
        cls, user: AbstractUser
    ) -> AbstractUser:
        """
        Configure two-factor auth for a user.

        :param user: The user the two-factor configuration is for.
        :return: The updated user. # TODO:
        """

        # user = UserHandler().change_password(user, old_password, new_password)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
