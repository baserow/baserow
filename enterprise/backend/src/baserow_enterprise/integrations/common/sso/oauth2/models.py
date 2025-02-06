from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow_enterprise.sso.oauth2.models import OpenIdConnectAuthProviderModelMixin


class OpenIdConnectAppAuthProviderModel(
    OpenIdConnectAuthProviderModelMixin, AppAuthProvider
):
    pass
