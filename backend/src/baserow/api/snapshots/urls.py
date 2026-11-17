from django.urls import re_path

from .views import (
    ApplicationSnapshotKeepView,
    RestoreSnapshotView,
    SnapshotsView,
    SnapshotUsageView,
    SnapshotView,
    WorkspaceSnapshotSettingsView,
)

app_name = "baserow.api.snapshot"


urlpatterns = [
    re_path(
        r"^application/(?P<application_id>[0-9]+)/$",
        SnapshotsView.as_view(),
        name="list",
    ),
    re_path(
        r"^application/(?P<application_id>[0-9]+)/usage/$",
        SnapshotUsageView.as_view(),
        name="usage",
    ),
    re_path(
        r"^application/(?P<application_id>[0-9]+)/keep/$",
        ApplicationSnapshotKeepView.as_view(),
        name="application_keep",
    ),
    re_path(
        r"^workspace/(?P<workspace_id>[0-9]+)/$",
        WorkspaceSnapshotSettingsView.as_view(),
        name="workspace",
    ),
    re_path(
        r"(?P<snapshot_id>[0-9]+)/$",
        SnapshotView.as_view(),
        name="item",
    ),
    re_path(
        r"(?P<snapshot_id>[0-9]+)/restore/$",
        RestoreSnapshotView.as_view(),
        name="restore",
    ),
]
