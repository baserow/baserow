from django.urls import re_path

from .views import AdminViewRotateSlugView, AdminViewsView, AdminViewView

app_name = "baserow.contrib.database.api.admin.views"

urlpatterns = [
    re_path(r"^$", AdminViewsView.as_view(), name="list"),
    re_path(r"^(?P<view_id>[0-9]+)/$", AdminViewView.as_view(), name="edit"),
    re_path(
        r"^(?P<view_id>[0-9]+)/rotate-slug/$",
        AdminViewRotateSlugView.as_view(),
        name="rotate_slug",
    ),
]
