from django.urls import include, path, re_path

from .data_sources import urls as data_source_urls
from .public import urls as public_urls
from .views import DashboardSharingView, RotateDashboardSlugView
from .widgets import urls as widget_urls

app_name = "baserow.contrib.dashboard.api"


urlpatterns = [
    path("", include(widget_urls, namespace="widgets")),
    path("", include(data_source_urls, namespace="data_sources")),
    path("public/", include(public_urls, namespace="public")),
    re_path(
        r"(?P<dashboard_id>[0-9]+)/sharing/$",
        DashboardSharingView.as_view(),
        name="sharing",
    ),
    re_path(
        r"(?P<dashboard_id>[0-9]+)/rotate-slug/$",
        RotateDashboardSlugView.as_view(),
        name="rotate_slug",
    ),
]
