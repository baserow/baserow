from django.urls import re_path

from baserow.contrib.dashboard.api.widgets.views import (
    WidgetLayoutDeleteView,
    WidgetLayoutView,
    WidgetsView,
    WidgetView,
)

app_name = "baserow.contrib.database.api.widgets"


urlpatterns = [
    re_path(
        r"(?P<dashboard_id>[0-9]+)/widgets/layout/$",
        WidgetLayoutView.as_view(),
        name="layout",
    ),
    re_path(
        r"(?P<dashboard_id>[0-9]+)/widgets/layout/delete/$",
        WidgetLayoutDeleteView.as_view(),
        name="layout-delete",
    ),
    re_path(
        r"(?P<dashboard_id>[0-9]+)/widgets/$",
        WidgetsView.as_view(),
        name="list",
    ),
    re_path(r"widgets/(?P<widget_id>[0-9]+)/$", WidgetView.as_view(), name="item"),
]
