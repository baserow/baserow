from django.urls import path

from baserow.api.agents.views import AgentView, WorkspaceAgentsView

app_name = "baserow.api.agents"

urlpatterns = [
    path(
        "workspace/<int:workspace_id>/", WorkspaceAgentsView.as_view(), name="workspace"
    ),
    path("<int:agent_id>/", AgentView.as_view(), name="item"),
]
