from baserow_enterprise.integrations.common.sso.saml.models import (
    SamlAppAuthProviderModel,
)
from baserow_enterprise.sso.saml.handler import SamlAuthProviderHandler


class SamlAppAuthProviderHandler(SamlAuthProviderHandler):
    model_class = SamlAppAuthProviderModel
