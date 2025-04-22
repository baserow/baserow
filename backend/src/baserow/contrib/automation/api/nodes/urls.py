from django.urls import re_path

from baserow.contrib.automation.api.nodes.views import (
    AutomationNodesView
)

app_name = "baserow.contrib.automation.api.nodes"

urlpatterns = [
    re_path(
        r"workflows/(?P<workflow_id>[0-9]+)/nodes/$",
        AutomationNodesView.as_view(),
        name="list",
    ),
]
