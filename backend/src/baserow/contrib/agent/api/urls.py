from django.urls import path

from .views import (
    AgentConfigurationView,
    AgentConversationsView,
    AgentMessagesView,
    AgentReadinessView,
)

app_name = "baserow.contrib.agent"

urlpatterns = [
    path("<int:agent_id>/readiness/", AgentReadinessView.as_view(), name="readiness"),
    path(
        "<int:agent_id>/configuration/",
        AgentConfigurationView.as_view(),
        name="configuration",
    ),
    path(
        "<int:agent_id>/conversations/",
        AgentConversationsView.as_view(),
        name="conversations",
    ),
    path(
        "<int:agent_id>/conversations/<uuid:conversation_uuid>/messages/",
        AgentMessagesView.as_view(),
        name="messages",
    ),
]
