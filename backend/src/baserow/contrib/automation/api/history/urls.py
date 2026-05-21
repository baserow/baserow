from django.urls import re_path

from baserow.contrib.automation.api.history.views import (
    AutomationNodeHistoriesView,
    AutomationNodeResultView,
)

app_name = "baserow.contrib.automation.api.history"

urlpatterns = [
    re_path(
        r"workflow_histories/(?P<workflow_history_id>[0-9]+)/node_histories/$",
        AutomationNodeHistoriesView.as_view(),
        name="node_histories",
    ),
    re_path(
        r"node_histories/(?P<node_history_id>[0-9]+)/result/$",
        AutomationNodeResultView.as_view(),
        name="node_result",
    ),
]
