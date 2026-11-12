from django.urls import include, path

from .triggers import urls as triggers_urls
from .views import (
    AgentApplicationView,
    AgentConfigurationView,
    AgentConversationsView,
    AgentConversationView,
    AgentMessagesView,
    AgentRunAsSubjectsView,
    AgentToolApprovalsView,
)

app_name = "baserow.contrib.agent"

urlpatterns = [
    path("<int:agent_id>/", AgentApplicationView.as_view(), name="item"),
    path(
        "<int:agent_id>/configuration/",
        AgentConfigurationView.as_view(),
        name="configuration",
    ),
    path(
        "<int:agent_id>/run-as-subjects/",
        AgentRunAsSubjectsView.as_view(),
        name="run_as_subjects",
    ),
    path(
        "<int:agent_id>/conversations/",
        AgentConversationsView.as_view(),
        name="conversations",
    ),
    path(
        "<int:agent_id>/conversations/<uuid:conversation_uuid>/",
        AgentConversationView.as_view(),
        name="conversation",
    ),
    path(
        "<int:agent_id>/conversations/<uuid:conversation_uuid>/messages/",
        AgentMessagesView.as_view(),
        name="messages",
    ),
    path(
        "<int:agent_id>/conversations/<uuid:conversation_uuid>/approvals/",
        AgentToolApprovalsView.as_view(),
        name="approvals",
    ),
    path("", include(triggers_urls, namespace="triggers")),
]
