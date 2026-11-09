from django.urls import path

from .views import (
    MCPClientMetadataView,
    MCPServerOAuthCompleteView,
    MCPServerOAuthDisconnectView,
    MCPServerOAuthStartView,
    MCPServerRefreshToolsView,
    MCPServerToolsView,
)

app_name = "baserow.contrib.integrations.mcp"

urlpatterns = [
    path(
        "<int:integration_id>/refresh-tools/",
        MCPServerRefreshToolsView.as_view(),
        name="refresh_tools",
    ),
    path("<int:integration_id>/tools/", MCPServerToolsView.as_view(), name="tools"),
    path(
        "<int:integration_id>/oauth/start/",
        MCPServerOAuthStartView.as_view(),
        name="oauth_start",
    ),
    path(
        "<int:integration_id>/oauth/disconnect/",
        MCPServerOAuthDisconnectView.as_view(),
        name="oauth_disconnect",
    ),
    path(
        "oauth/complete/", MCPServerOAuthCompleteView.as_view(), name="oauth_complete"
    ),
    path(
        "oauth/client-metadata.json",
        MCPClientMetadataView.as_view(),
        name="oauth_client_metadata",
    ),
]
