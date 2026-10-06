from django.urls import re_path

from baserow_premium.api.row_comments.views import (
    RowCommentMentionablesView,
    RowCommentsNotificationModeView,
    RowCommentsView,
    RowCommentView,
)

app_name = "baserow_premium.api.row_comments"

urlpatterns = [
    re_path(
        r"^(?P<table_id>[0-9]+)/(?P<row_id>[0-9]+)/$",
        RowCommentsView.as_view(),
        name="list",
    ),
    re_path(
        r"^(?P<table_id>[0-9]+)/comment/(?P<comment_id>[0-9]+)/$",
        RowCommentView.as_view(),
        name="item",
    ),
    re_path(
        r"^(?P<table_id>[0-9]+)/mentionables/$",
        RowCommentMentionablesView.as_view(),
        name="mentionables",
    ),
    re_path(
        r"^(?P<table_id>[0-9]+)/(?P<row_id>[0-9]+)/notification-mode/$",
        RowCommentsNotificationModeView.as_view(),
        name="notification_mode",
    ),
]
