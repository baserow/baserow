from django.urls import path

from .views import AgentConfigurationView, AgentReadinessView

app_name = "baserow.contrib.agent"

urlpatterns = [
    path("<int:agent_id>/readiness/", AgentReadinessView.as_view(), name="readiness"),
    path(
        "<int:agent_id>/configuration/",
        AgentConfigurationView.as_view(),
        name="configuration",
    ),
]
