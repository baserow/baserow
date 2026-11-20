from django.urls import path

from .views import (
    OAuthAccountCompleteView,
    OAuthAccountConfigView,
    OAuthAccountDisconnectView,
    OAuthAccountStartView,
)

app_name = "baserow.contrib.integrations.oauth_account"

urlpatterns = [
    path(
        "<str:integration_type>/config/",
        OAuthAccountConfigView.as_view(),
        name="config",
    ),
    path(
        "<str:integration_type>/start/", OAuthAccountStartView.as_view(), name="start"
    ),
    path(
        "<str:integration_type>/complete/",
        OAuthAccountCompleteView.as_view(),
        name="complete",
    ),
    path(
        "<str:integration_type>/<int:integration_id>/disconnect/",
        OAuthAccountDisconnectView.as_view(),
        name="disconnect",
    ),
]
