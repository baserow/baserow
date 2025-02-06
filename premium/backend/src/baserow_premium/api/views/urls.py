from django.urls import re_path

from baserow_premium.api.views.views import (
    ExportPublicViewJobView,
    ExportPublicViewView,
    PremiumViewAttributesView,
)

app_name = "baserow_premium.api.views"

urlpatterns = [
    re_path(
        "(?P<view_id>[0-9]+)/premium$",
        PremiumViewAttributesView.as_view(),
        name="premium_view_attributes",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/export-public-view/$",
        ExportPublicViewView.as_view(),
        name="export_public_view",
    ),
    re_path(
        r"get-public-view-export/(?P<job_id>[-\w.]+)/$",
        ExportPublicViewJobView.as_view(),
        name="get_public_view_export",
    ),
]
