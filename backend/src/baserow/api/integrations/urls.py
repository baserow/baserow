from django.urls import re_path

from baserow.api.integrations.oauth2.views import (
    OAuth2AuthorizeView,
    OAuth2CallbackView,
)
from baserow.api.integrations.views import (
    IntegrationsView,
    IntegrationView,
    MoveIntegrationView,
)

app_name = "baserow.api.integrations"

urlpatterns = [
    re_path(
        r"application/(?P<application_id>[0-9]+)/integrations/$",
        IntegrationsView.as_view(),
        name="list",
    ),
    re_path(
        r"integration/(?P<integration_id>[0-9]+)/$",
        IntegrationView.as_view(),
        name="item",
    ),
    re_path(
        r"integration/(?P<integration_id>[0-9]+)/move/$",
        MoveIntegrationView.as_view(),
        name="move",
    ),
    re_path(
        r"integration/(?P<integration_id>[0-9]+)/oauth2/authorize/$",
        OAuth2AuthorizeView.as_view(),
        name="oauth2_authorize",
    ),
    re_path(
        r"integration/oauth2/callback/$",
        OAuth2CallbackView.as_view(),
        name="oauth2_callback",
    ),
]
