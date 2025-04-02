from django.db import models

from baserow.contrib.dashboard.widgets.models import Widget


class ChartWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )
