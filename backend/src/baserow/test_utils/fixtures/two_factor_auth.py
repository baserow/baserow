from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from baserow.core.two_factor_auth.models import TOTPAuthProviderModel
from baserow.core.two_factor_auth.registries import TOTPAuthProviderType

User = get_user_model()


class TwoFactorAuthFixtures:
    def configure_totp(self, user: AbstractUser, **kwargs) -> TOTPAuthProviderModel:
        provider = TOTPAuthProviderType().configure(user)
        # TODO: finished configuration
        return provider
