from django.urls import re_path

from baserow.contrib.automation.api.workflows.views import OrderWorkflowsView, WorkflowsView, WorkflowView

app_name = "baserow.contrib.automation.api.workflows"

urlpatterns_with_automation_id = [
    re_path(
        r"$",
        WorkflowsView.as_view(),
        name="create",
    ),
    re_path(r"order/$", OrderWorkflowsView.as_view(), name="order"),
]

urlpatterns_without_automation_id = [
    re_path(r"(?P<workflow_id>[0-9]+)/$", WorkflowView.as_view(), name="automation_workflow"),
]
