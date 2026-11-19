from django.urls import path

from .views import (
    GoogleOAuthCompleteView,
    GoogleOAuthConfigView,
    GoogleOAuthDisconnectView,
    GoogleOAuthStartView,
)

urlpatterns = [
    path("oauth/config/", GoogleOAuthConfigView.as_view(), name="config"),
    path(
        "<int:integration_id>/oauth/start/",
        GoogleOAuthStartView.as_view(),
        name="start",
    ),
    path(
        "<int:integration_id>/oauth/disconnect/",
        GoogleOAuthDisconnectView.as_view(),
        name="disconnect",
    ),
    path("oauth/complete/", GoogleOAuthCompleteView.as_view(), name="complete"),
]
