from django.urls import path

from .views import AgentChannelsView, AgentChannelView

app_name = "baserow.contrib.agent.api.channels"

urlpatterns = [
    path("<int:agent_id>/channels/", AgentChannelsView.as_view(), name="list"),
    path(
        "<int:agent_id>/channels/<int:channel_id>/",
        AgentChannelView.as_view(),
        name="item",
    ),
]
