from django.urls import path

from .views import AgentTriggersView, AgentTriggerTypesView, AgentTriggerView

app_name = "baserow.contrib.agent.api.triggers"

urlpatterns = [
    path("<int:agent_id>/triggers/", AgentTriggersView.as_view(), name="list"),
    path(
        "<int:agent_id>/triggers/<int:trigger_id>/",
        AgentTriggerView.as_view(),
        name="item",
    ),
    path(
        "<int:agent_id>/trigger-types/",
        AgentTriggerTypesView.as_view(),
        name="types",
    ),
]
