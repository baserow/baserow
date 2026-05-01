from django.urls import include, path, re_path

from .comments import urls as comment_urls
from .views import WhiteboardView

app_name = "baserow.contrib.whiteboard.api"

urlpatterns = [
    re_path(
        r"^(?P<whiteboard_id>[0-9]+)/$",
        WhiteboardView.as_view(),
        name="item",
    ),
    path("", include(comment_urls, namespace="comments")),
]
