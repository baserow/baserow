from typing import cast

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.two_factor_auth.exceptions import (
    TwoFactorAuthCannotBeConfigured,
    TwoFactorAuthNotConfigured,
    WrongPassword,
)
from baserow.core.two_factor_auth.registries import TwoFactorAuthProviderType

from .models import TwoFactorAuthProviderModel
from .registries import two_factor_auth_type_registry
from .types import TwoFactorProviderForUpdate


class TwoFactorAuthHandler:
    def get_provider(
        self, user: AbstractUser, base_queryset: QuerySet | None = None
    ) -> TwoFactorAuthProviderModel | None:
        """
        Returns the user's provider from the database or None if no
        provider is configured yet.

        :param user: The user the provider is for.
        :param base_queryset: The base queryset to use to build the query.
        :return: The provider instance.
        """

        queryset = (
            base_queryset if base_queryset else TwoFactorAuthProviderModel.objects.all()
        )

        provider = queryset.filter(user=user).first()
        if provider is None:
            return None

        provider_specific: TwoFactorAuthProviderModel = provider.specific
        return provider_specific

    def get_provider_for_update(
        self,
        user: AbstractUser,
    ) -> TwoFactorProviderForUpdate | None:
        """
        Returns the user's provider from the database or None if no
        provider is configured yet.

        :param user: The user the provider is for.
        :return: The provider instance.
        """

        queryset = TwoFactorAuthProviderModel.objects.all().select_for_update(
            of=("self",)
        )
        provider = self.get_provider(
            user,
            base_queryset=queryset,
        )
        if provider is None:
            return None

        return cast(
            TwoFactorProviderForUpdate,
            provider,
        )

    def configure_provider(
        self,
        provider_type_str: str,
        user: AbstractUser,
        **kwargs,
    ) -> TwoFactorAuthProviderModel:
        """
        Configures the provider type for the user.

        :param provider_type_str: The two-factor auth type of the provider.
        :param user: The user configuring the authentication.
        :param kwargs: Additional attributes of the provider.
        :return: The created two-factor auth provider model.
        """

        # Two-factor auth is only for password-based accounts.
        # Accounts that don't have password set are accounts
        # created via SSO.
        if user.password == "":  # nosec
            raise TwoFactorAuthCannotBeConfigured

        provider_type: TwoFactorAuthProviderType = two_factor_auth_type_registry.get(
            provider_type_str
        )

        provider = self.get_provider_for_update(user)
        provider = provider_type.configure(user, provider, **kwargs)
        provider.save()
        return provider

    def disable(self, user: AbstractUser, password: str):
        """
        Disables any configured provider for the user.

        :param user: The user for whom to disable the authentication.
        :param password: Password for confirmation.
        :raises WrongPassword: If the provided password doesn't match.
        """

        if not user.check_password(password):
            raise WrongPassword

        provider = self.get_provider_for_update(user)
        if provider:
            provider_type = provider.get_type()
            provider_type.disable(provider, user)
        else:
            raise TwoFactorAuthNotConfigured

    def verify(self, provider_type_str: str, **kwargs) -> bool:
        """
        Verifies 2fa of the provider type.

        :param provider_type_str: The two-factor auth type of the provider.
        :param kwargs: Additional verification attributes of the provider.
        :return: If the verification request is accepted.
        """

        provider_type: TwoFactorAuthProviderType = two_factor_auth_type_registry.get(
            provider_type_str
        )
        return provider_type.verify(**kwargs)
