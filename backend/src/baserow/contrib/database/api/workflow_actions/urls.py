from django.urls import re_path

from baserow.contrib.database.api.workflow_actions.views import (
    DatabaseWorkflowActionsView,
    DatabaseWorkflowActionView,
)

app_name = "baserow.contrib.database.api.workflow_actions"

urlpatterns = [
    re_path(
        r"field/(?P<field_id>[0-9]+)/workflow_actions/$",
        DatabaseWorkflowActionsView.as_view(),
        name="list",
    ),
    re_path(
        r"workflow_action/(?P<workflow_action_id>[0-9]+)/$",
        DatabaseWorkflowActionView.as_view(),
        name="item",
    ),
]
