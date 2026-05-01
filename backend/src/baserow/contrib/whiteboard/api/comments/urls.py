from django.urls import re_path

from .views import (
    WhiteboardCommentResolveView,
    WhiteboardCommentsView,
    WhiteboardCommentView,
)

app_name = "baserow.contrib.whiteboard.api.comments"

urlpatterns = [
    re_path(
        r"^(?P<whiteboard_id>[0-9]+)/comments/$",
        WhiteboardCommentsView.as_view(),
        name="list",
    ),
    re_path(
        r"^comments/(?P<comment_id>[0-9]+)/$",
        WhiteboardCommentView.as_view(),
        name="item",
    ),
    re_path(
        r"^comments/(?P<comment_id>[0-9]+)/resolve/$",
        WhiteboardCommentResolveView.as_view(),
        name="resolve",
    ),
]
