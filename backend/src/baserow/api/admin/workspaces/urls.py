from django.urls import re_path

from baserow.api.admin.workspaces.views import WorkspaceAdminView, WorkspacesAdminView

app_name = "baserow.api.admin.workspaces"

urlpatterns = [
    re_path(r"^$", WorkspacesAdminView.as_view(), name="list"),
    re_path(r"^(?P<workspace_id>[0-9]+)/$", WorkspaceAdminView.as_view(), name="edit"),
]
