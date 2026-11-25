from django.urls import path

from .views import (
    AgentParticipationRuleOptionsView,
    AgentParticipationRulesView,
    AgentParticipationRuleView,
)

app_name = "baserow_enterprise.api.agent_permissions"

urlpatterns = [
    path(
        "<int:agent_id>/permissions/",
        AgentParticipationRulesView.as_view(),
        name="rules",
    ),
    path(
        "<int:agent_id>/permissions/options/",
        AgentParticipationRuleOptionsView.as_view(),
        name="options",
    ),
    path(
        "<int:agent_id>/permissions/<str:capability>/",
        AgentParticipationRuleView.as_view(),
        name="rule",
    ),
]
