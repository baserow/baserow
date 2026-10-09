from django.urls import path

from baserow_enterprise.agent_builder.api.views import (
    AgentsView,
    AgentView,
    OrderAgentsView,
)

app_name = "baserow_enterprise.agent_builder.api"

urlpatterns = [
    path("<int:agent_builder_id>/agents/", AgentsView.as_view(), name="agents"),
    path(
        "<int:agent_builder_id>/agents/order/", OrderAgentsView.as_view(), name="order"
    ),
    path("agents/<int:agent_id>/", AgentView.as_view(), name="agent"),
]
