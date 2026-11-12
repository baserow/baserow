from django.urls import path

from .views import AgentActionsView, AgentActionView

app_name = "baserow.contrib.agent.api.action_tools"

urlpatterns = [
    path("<int:agent_id>/actions/", AgentActionsView.as_view(), name="list"),
    path(
        "<int:agent_id>/actions/<int:action_id>/",
        AgentActionView.as_view(),
        name="item",
    ),
]
