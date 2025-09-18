import dataclasses
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)

from django.contrib.auth.models import AbstractUser

from baserow.core.action.scopes import RootActionScopeType
from baserow.core.two_factor_auth.handler import TwoFactorAuthHandler
from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel


class ConfigureTwoFactorAuthActionType(ActionType):
    type = "configure_two_factor_auth"
    description = ActionTypeDescription(
        _("Configure two-factor authentication"),
        _(
            'User "%(user_email)s" (%(user_id)s) configured %(provider_type)s two-factor authentication.'
        ),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        provider_type: str

    @classmethod
    def do(cls, user: AbstractUser, provider_type: str) -> TwoFactorAuthProviderModel:
        """
        Configure two-factor auth for a user.

        :param user: The user the two-factor configuration is for.
        :param provider_type: The provider type the configuration is for.
        :return: The updated provider.
        """

        provider = TwoFactorAuthHandler().configure_provider(provider_type, user)

        cls.register_action(
            user=user,
            params=cls.Params(user.id, user.email, provider_type),
            scope=cls.scope(),
        )

        return provider

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
