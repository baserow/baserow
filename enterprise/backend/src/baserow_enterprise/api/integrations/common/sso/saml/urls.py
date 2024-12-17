from django.urls import path

from .views import (
    SamlAppAuthProviderAssertionConsumerServiceView,
    SamlAppAuthProviderBaserowInitiatedSingleSignOn,
)

app_name = "baserow_enterprise.api.integrations.common.sso.saml"

urlpatterns = [
    path(
        "user-source/<str:user_source_uid>/sso/saml/login/",
        SamlAppAuthProviderBaserowInitiatedSingleSignOn.as_view(),
        name="login",
    ),
    path(
        "user-source/sso/saml/acs/",
        SamlAppAuthProviderAssertionConsumerServiceView.as_view(),
        name="acs",
    ),
]
