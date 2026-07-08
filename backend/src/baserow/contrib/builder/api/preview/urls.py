from django.urls import re_path

from baserow.contrib.builder.api.preview.views import (
    BuilderPreviewCurrentView,
    BuilderPreviewExchangeView,
    BuilderPreviewGrantView,
)

app_name = "baserow.contrib.builder.api.preview"

urlpatterns = [
    re_path(
        r"(?P<builder_id>[0-9]+)/grant/$",
        BuilderPreviewGrantView.as_view(),
        name="grant",
    ),
    re_path(
        r"exchange/(?P<token>[^/]+)/$",
        BuilderPreviewExchangeView.as_view(),
        name="exchange",
    ),
    re_path(
        r"current/$",
        BuilderPreviewCurrentView.as_view(),
        name="current",
    ),
]
