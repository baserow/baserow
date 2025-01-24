from django.urls import include, path

from .data_sources import urls as data_source_urls
from .widgets import urls as widget_urls

app_name = "baserow.contrib.dashboard.api"


urlpatterns = [
    path("", include(widget_urls, namespace="widgets")),
    path("", include(data_source_urls, namespace="data_sources")),
]
