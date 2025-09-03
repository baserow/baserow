import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType
from baserow.core.two_factor_auth.handler import TwoFactorAuthHandler
from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel


class ConfigureTwoFactorAuthActionType(ActionType):
    type = "configure_two_factor_auth"
    description = ActionTypeDescription(
        _("Configure two-factor authentication"),
        _(
            'User "%(user_email)s" (%(user_id)s) configured %(provider_type)s (enabled %(is_enabled)s)'
            " two-factor authentication."
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
        is_enabled: bool

    @classmethod
    def do(
        cls, user: AbstractUser, provider_type: str, **kwargs
    ) -> TwoFactorAuthProviderModel:
        """
        Configure two-factor auth for a user.

        :param user: The user the two-factor configuration is for.
        :param provider_type: The provider type the configuration is for.
        :param kwargs: Additional arguments for the provider.
        :return: The updated provider.
        """

        provider = TwoFactorAuthHandler().configure_provider(
            provider_type, user, **kwargs
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                user.id, user.email, provider_type, is_enabled=provider.is_enabled
            ),
            scope=cls.scope(),
        )

        return provider

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class DisableTwoFactorAuthActionType(ActionType):
    type = "disable_two_factor_auth"
    description = ActionTypeDescription(
        _("Disable two-factor authentication"),
        _('User "%(user_email)s" (%(user_id)s) disabled two-factor authentication.'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, user: AbstractUser, password: str) -> None:
        """
        Disable two-factor auth for a user.

        :param user: The user the two-factor configuration is for.
        :param password: The user's password for confirmation.
        """

        TwoFactorAuthHandler().disable(user, password)

        cls.register_action(
            user=user,
            params=cls.Params(user.id, user.email),
            scope=cls.scope(),
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
