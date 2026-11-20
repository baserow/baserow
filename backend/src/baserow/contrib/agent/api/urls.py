from django.urls import include, path

from .action_tools import urls as action_tools_urls
from .triggers import urls as triggers_urls
from .views import (
    AgentApplicationView,
    AgentConfigurationView,
    AgentConversationsView,
    AgentConversationView,
    AgentMessagesView,
    AgentPendingApprovalsView,
    AgentRunAsIdentitiesView,
    AgentToolApprovalsView,
    AgentToolsView,
)

app_name = "baserow.contrib.agent"

urlpatterns = [
    path(
        "tools/workspace/<int:workspace_id>/",
        AgentToolsView.as_view(),
        name="tools",
    ),
    path("<int:agent_id>/", AgentApplicationView.as_view(), name="item"),
    path(
        "<int:agent_id>/configuration/",
        AgentConfigurationView.as_view(),
        name="configuration",
    ),
    path(
        "<int:agent_id>/run-as-identities/",
        AgentRunAsIdentitiesView.as_view(),
        name="run_as_identities",
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
    path(
        "<int:agent_id>/pending-approvals/",
        AgentPendingApprovalsView.as_view(),
        name="pending_approvals",
    ),
    path("", include(triggers_urls, namespace="triggers")),
    path("", include(action_tools_urls, namespace="actions")),
]
