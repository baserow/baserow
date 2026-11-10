from django.urls import re_path

from .views import (
    PublicDashboardAuthView,
    PublicDashboardDataSourceDispatchView,
    PublicDashboardInfoView,
)

app_name = "baserow.contrib.dashboard.api.public"

urlpatterns = [
    re_path(
        r"(?P<slug>[-\w]+)/$",
        PublicDashboardInfoView.as_view(),
        name="info",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/auth/$",
        PublicDashboardAuthView.as_view(),
        name="auth",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/data-sources/(?P<data_source_id>[0-9]+)/dispatch/$",
        PublicDashboardDataSourceDispatchView.as_view(),
        name="data_source_dispatch",
    ),
]
