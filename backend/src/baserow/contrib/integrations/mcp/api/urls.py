from django.urls import path

from .views import MCPServerRefreshToolsView, MCPServerToolsView

app_name = "baserow.contrib.integrations.mcp"

urlpatterns = [
    path(
        "<int:integration_id>/refresh-tools/",
        MCPServerRefreshToolsView.as_view(),
        name="refresh_tools",
    ),
    path("<int:integration_id>/tools/", MCPServerToolsView.as_view(), name="tools"),
]
