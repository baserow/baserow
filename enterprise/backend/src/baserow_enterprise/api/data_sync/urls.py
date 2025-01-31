from django.urls import re_path

from .views import PeriodicDataSyncIntervalView

app_name = "baserow_enterprise.api.data_sync"

urlpatterns = [
    re_path(
        r"(?P<data_sync_id>[0-9]+)/periodic-interval/$",
        PeriodicDataSyncIntervalView.as_view(),
        name="periodic_interval",
    ),
]
