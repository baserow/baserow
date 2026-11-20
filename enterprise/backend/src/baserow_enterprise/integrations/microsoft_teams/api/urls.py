from django.urls import path, re_path

from .views import (
    MicrosoftTeamsChannelsView,
    MicrosoftTeamsChatsView,
    MicrosoftTeamsTeamsView,
)

app_name = "baserow_enterprise.integrations.microsoft_teams"

urlpatterns = [
    path(
        "<int:integration_id>/teams/", MicrosoftTeamsTeamsView.as_view(), name="teams"
    ),
    # Team ids hold `:` and `@`, so anything but a `/`.
    re_path(
        r"^(?P<integration_id>[0-9]+)/teams/(?P<team_id>[^/]+)/channels/$",
        MicrosoftTeamsChannelsView.as_view(),
        name="channels",
    ),
    path(
        "<int:integration_id>/chats/", MicrosoftTeamsChatsView.as_view(), name="chats"
    ),
]
