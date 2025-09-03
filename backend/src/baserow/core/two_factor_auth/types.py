from typing import NewType

from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel

TwoFactorProviderForUpdate = NewType(
    "TwoFactorProviderForUpdate", TwoFactorAuthProviderModel
)
