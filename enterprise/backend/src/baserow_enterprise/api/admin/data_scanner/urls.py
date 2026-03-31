from django.urls import re_path

from .views import (
    DataScanDetailView,
    DataScanListView,
    DataScanResultDeleteView,
    DataScanResultExportView,
    DataScanResultListView,
    DataScanTriggerView,
    DataScanWorkspaceStructureView,
)

app_name = "baserow_enterprise.api.admin.data_scanner"

urlpatterns = [
    re_path(r"^scans/$", DataScanListView.as_view(), name="list"),
    re_path(
        r"^scans/(?P<scan_id>[0-9]+)/$",
        DataScanDetailView.as_view(),
        name="detail",
    ),
    re_path(
        r"^scans/(?P<scan_id>[0-9]+)/trigger/$",
        DataScanTriggerView.as_view(),
        name="trigger",
    ),
    re_path(r"^results/$", DataScanResultListView.as_view(), name="results"),
    re_path(
        r"^results/export/$",
        DataScanResultExportView.as_view(),
        name="results_export",
    ),
    re_path(
        r"^results/(?P<result_id>[0-9]+)/$",
        DataScanResultDeleteView.as_view(),
        name="result_delete",
    ),
    re_path(
        r"^workspace-structure/(?P<workspace_id>[0-9]+)/$",
        DataScanWorkspaceStructureView.as_view(),
        name="workspace_structure",
    ),
]
