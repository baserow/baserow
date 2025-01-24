from django.urls import re_path

from baserow.api.admin.dashboard.views import AdminDashboardView

app_name = "baserow.api.admin.dashboard"

urlpatterns = [
    re_path(r"^$", AdminDashboardView.as_view(), name="dashboard"),
]
