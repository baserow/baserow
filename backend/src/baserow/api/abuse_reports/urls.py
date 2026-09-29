from django.urls import re_path

from .views import AbuseReportsView

app_name = "baserow.api.abuse_reports"

urlpatterns = [
    re_path(r"^$", AbuseReportsView.as_view(), name="create"),
]
