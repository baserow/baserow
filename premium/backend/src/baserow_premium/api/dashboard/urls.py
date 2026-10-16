from django.urls import re_path

from baserow_premium.api.dashboard.views import PremiumDashboardAttributesView

app_name = "baserow_premium.api.dashboard"

urlpatterns = [
    re_path(
        r"(?P<dashboard_id>[0-9]+)/premium/$",
        PremiumDashboardAttributesView.as_view(),
        name="premium_dashboard_attributes",
    ),
]
