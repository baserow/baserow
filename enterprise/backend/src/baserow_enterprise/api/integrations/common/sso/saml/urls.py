from django.urls import re_path

from .views import (
    SamlAppAuthProviderAssertionConsumerServiceView,
    SamlAppAuthProviderBaserowInitiatedSingleSignOn,
)

app_name = "baserow_enterprise.api.integrations.common.sso.saml"

urlpatterns = [
    re_path(
        r"acs/$", SamlAppAuthProviderAssertionConsumerServiceView.as_view(), name="acs"
    ),
    re_path(
        r"login/$",
        SamlAppAuthProviderBaserowInitiatedSingleSignOn.as_view(),
        name="login",
    ),
]
