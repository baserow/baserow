from django.urls import re_path

from .views import AdminWorkspaceListView

app_name = "baserow_enterprise.api.admin.workspaces"

urlpatterns = [
    re_path(r"^$", AdminWorkspaceListView.as_view(), name="list"),
]
