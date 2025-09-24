from typing import cast

from django.db.models import QuerySet

from baserow.core.two_factor_auth.registries import TwoFactorAuthProviderType
from baserow.core.utils import extract_allowed
from .registries import two_factor_auth_type_registry
from .models import TwoFactorAuthProviderModel
from .types import TwoFactorProviderForUpdate
from django.contrib.auth.models import AbstractUser


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

        queryset = base_queryset if base_queryset else TwoFactorAuthProviderModel.objects.all()

        provider = queryset.filter(user=user).first()
        if provider is None:
            return None

        provider_specific: TwoFactorAuthProviderModel = provider.specific
        return provider_specific

    def get_provider_for_update(
        self, user: AbstractUser,
    ) -> TwoFactorProviderForUpdate | None:
        """
        Returns the user's provider from the database or None if no
        provider is configured yet.

        :param user: The user the provider is for.
        :return: The provider instance.
        """

        queryset = TwoFactorAuthProviderModel.objects.all().select_for_update(of=("self",))
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

        :param provider_type: The two-factor auth type of the provider.
        :param user: The user configuring the authentication.
        :param kwargs: Additional attributes of the provider.
        :return: The created two-factor auth provider model.
        """

        provider_type: TwoFactorAuthProviderType = two_factor_auth_type_registry.get(
            provider_type_str
        )

        # allowed_values = {}  # TODO: extract_allowed(kwargs, provider_type.allowed_fields)
        # allowed_values["user"] = user

        # allowed_values = provider_type.prepare_value_for_db(allowed_values)

        # model_class = cast(TwoFactorAuthProviderModel, provider_type.model_class)
        # provider = provider_type.model_class(**allowed_values)
        # provider._ensure_content_type_is_set()
        # provider.full_clean()

        provider = self.get_provider_for_update(user)
        provider = provider_type.configure(user, provider, **kwargs)
        provider.save()

        return provider
