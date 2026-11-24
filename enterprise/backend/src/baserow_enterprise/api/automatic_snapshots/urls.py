from django.urls import re_path

from .views import (
    ApplicationAutomaticSnapshotScheduleView,
    BulkWorkspaceAutomaticSnapshotSchedulesView,
    WorkspaceAutomaticSnapshotSchedulesView,
)

app_name = "baserow_enterprise.api.automatic_snapshots"

urlpatterns = [
    re_path(
        r"^application/(?P<application_id>[0-9]+)/$",
        ApplicationAutomaticSnapshotScheduleView.as_view(),
        name="application",
    ),
    re_path(
        r"^workspace/(?P<workspace_id>[0-9]+)/$",
        WorkspaceAutomaticSnapshotSchedulesView.as_view(),
        name="workspace",
    ),
    re_path(
        r"^workspace/(?P<workspace_id>[0-9]+)/bulk/$",
        BulkWorkspaceAutomaticSnapshotSchedulesView.as_view(),
        name="workspace_bulk",
    ),
]
