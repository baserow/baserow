from django.urls import path

from .views import BroadcastChangesView, WhiteboardView

app_name = "baserow.contrib.whiteboard.api"

urlpatterns = [
    path(
        "<int:whiteboard_id>/",
        WhiteboardView.as_view(),
        name="item",
    ),
    path(
        "<int:whiteboard_id>/broadcast-changes/",
        BroadcastChangesView.as_view(),
        name="broadcast_changes",
    ),
]
