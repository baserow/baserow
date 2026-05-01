from django.urls import include, path, re_path

from .comments import urls as comment_urls
from .views import BroadcastChangesView, WhiteboardView

app_name = "baserow.contrib.whiteboard.api"

urlpatterns = [
    re_path(
        r"^(?P<whiteboard_id>[0-9]+)/$",
        WhiteboardView.as_view(),
        name="item",
    ),
    re_path(
        r"^(?P<whiteboard_id>[0-9]+)/broadcast-changes/$",
        BroadcastChangesView.as_view(),
        name="broadcast_changes",
    ),
    path("", include(comment_urls, namespace="comments")),
]
