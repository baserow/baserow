from django.urls import re_path

from .views import (
    DataSyncPropertiesView,
    DataSyncsView,
    DataSyncTypePropertiesView,
    DataSyncView,
    SyncDataSyncTableView,
)

app_name = "baserow.contrib.database.api.data_sync"
urlpatterns = [
    re_path(
        r"database/(?P<database_id>[0-9]+)/$", DataSyncsView.as_view(), name="list"
    ),
    re_path(r"(?P<data_sync_id>[0-9]+)/$", DataSyncView.as_view(), name="item"),
    re_path(
        r"(?P<data_sync_id>[0-9]+)/sync/async/$",
        SyncDataSyncTableView.as_view(),
        name="sync_table",
    ),
    re_path(
        r"properties/$",
        DataSyncTypePropertiesView.as_view(),
        name="properties",
    ),
    re_path(
        r"(?P<data_sync_id>[0-9]+)/properties/$",
        DataSyncPropertiesView.as_view(),
        name="properties_of_data_sync",
    ),
]
