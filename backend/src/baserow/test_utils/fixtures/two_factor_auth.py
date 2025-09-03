from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

import pyotp

from baserow.core.two_factor_auth.models import TOTPAuthProviderModel
from baserow.core.two_factor_auth.registries import TOTPAuthProviderType

User = get_user_model()


class TwoFactorAuthFixtures:
    def configure_base_totp(
        self, user: AbstractUser, **kwargs
    ) -> TOTPAuthProviderModel:
        provider = TOTPAuthProviderType().configure(user)
        provider.save()
        return provider

    def configure_totp(self, user: AbstractUser, **kwargs) -> TOTPAuthProviderModel:
        provider = self.configure_base_totp(user)
        totp = pyotp.TOTP(provider.secret)
        valid_code = totp.now()
        provider = TOTPAuthProviderType().configure(user, provider, code=valid_code)
        provider.save()
        return provider
