from django.urls import re_path

from baserow.contrib.dashboard.api.data_sources.views import (
    DashboardDataSourcesView,
    DashboardDataSourceView,
    DispatchDashboardDataSourceView,
)

app_name = "baserow.contrib.dashboard.api.data_sources"

urlpatterns = [
    re_path(
        r"(?P<dashboard_id>[0-9]+)/data-sources/$",
        DashboardDataSourcesView.as_view(),
        name="list",
    ),
    re_path(
        r"data-sources/(?P<data_source_id>[0-9]+)/$",
        DashboardDataSourceView.as_view(),
        name="item",
    ),
    re_path(
        r"data-sources/(?P<data_source_id>[0-9]+)/dispatch/$",
        DispatchDashboardDataSourceView.as_view(),
        name="dispatch",
    ),
]
