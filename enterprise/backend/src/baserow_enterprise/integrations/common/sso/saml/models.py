from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow_enterprise.sso.saml.models import SamlAuthProviderModelMixin


class SamlAppAuthProviderModel(SamlAuthProviderModelMixin, AppAuthProvider):
    # Restore ordering
    class Meta(AppAuthProvider.Meta):
        ordering = ["id"]
