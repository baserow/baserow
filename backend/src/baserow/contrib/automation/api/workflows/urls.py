from django.urls import re_path

from baserow.contrib.automation.api.workflows.views import WorkflowsView

app_name = "baserow.contrib.automation.api.workflows"

urlpatterns_with_automation_id = [
    re_path(
        r"$",
        WorkflowsView.as_view(),
        name="create",
    ),
]
